import logging
import math
import os
import re
import time
import ctypes
import xml.etree.ElementTree as ET
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

POINTS_TO_MM = 0.352778
UNIQUE_CODE_PATTERN = re.compile(r"\b\d{10}\b")
NESTING_ORDER_PATTERN = re.compile(r"NestingOrders\\([^\\]+)")


@dataclass(frozen=True)
class Settings:
    folder_to_monitor: Path
    cut_queue_folder: Path
    out_folder: Path
    save_folder: Path
    specific_file: str
    poll_interval_seconds: float = 1.0

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            folder_to_monitor=Path(_required_env("FOLDER_TO_MONITOR")),
            cut_queue_folder=Path(_required_env("CUT_QUEUE_FOLDER")),
            out_folder=Path(_required_env("OUT_FOLDER")),
            save_folder=Path(_required_env("SAVE_FOLDER")),
            specific_file=os.getenv("SPECIFIC_FILE", "LastProductionToExporter.xml"),
            poll_interval_seconds=float(os.getenv("POLL_INTERVAL_SECONDS", "1")),
        )


@dataclass(frozen=True)
class JobDetails:
    customer: str = "Unknown"
    submitted_by: str = "Unknown"
    quantity: str = "1"
    note: str = "None"
    width_mm: int = 0
    height_mm: int = 0


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def set_console_title(title: str) -> None:
    if os.name != "nt":
        return

    try:
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception:
        # Fall back quietly if the process is not attached to a standard console.
        pass


def safe_text(element: ET.Element | None, default: str = "") -> str:
    if element is None or element.text is None:
        return default
    return element.text.strip()


def safe_int(element: ET.Element | None, default: int = 0) -> int:
    try:
        return int(safe_text(element, str(default)))
    except ValueError:
        return default


def extract_unique_code(pdf_destination: str) -> str | None:
    match = UNIQUE_CODE_PATTERN.search(pdf_destination)
    return match.group(0) if match else None


def get_matching_cut_queue_xml(cut_queue_folder: Path, unique_code: str) -> Path | None:
    for path in cut_queue_folder.glob("*.xml"):
        if unique_code in path.name:
            return path
    return None


def extract_media(cut_queue_xml: Path) -> str | None:
    tree = ET.parse(cut_queue_xml)
    root = tree.getroot()
    media = safe_text(root.find(".//Media"))
    return media or None


def clean_filename(full_path: str) -> str:
    match = NESTING_ORDER_PATTERN.search(full_path)
    return match.group(1) if match else Path(full_path).name


def extract_job_counts(root: ET.Element, job_count: int) -> OrderedDict[str, dict]:
    aggregated_jobs: OrderedDict[str, dict] = OrderedDict()

    for index in range(job_count):
        job_tag = root.find(f".//Job{index}")
        if job_tag is None:
            continue

        original_name = safe_text(job_tag.find("PDFOrigFileName"))
        if not original_name:
            continue

        filename = clean_filename(original_name)
        job_ref = filename.split("_", 1)[0]
        placed_copies = safe_int(job_tag.find("PlacedCopies"), default=1)

        if filename not in aggregated_jobs:
            aggregated_jobs[filename] = {
                "job_ref": job_ref,
                "filename": filename,
                "placed_copies": 0,
            }

        aggregated_jobs[filename]["placed_copies"] += placed_copies

    return aggregated_jobs


def points_to_mm(value: str) -> int:
    try:
        return round(float(value) * POINTS_TO_MM)
    except (TypeError, ValueError):
        return 0


def load_job_details(out_folder: Path, filename: str) -> JobDetails:
    job_xml_path = out_folder / filename.replace(".pdf", ".xml")
    if not job_xml_path.exists():
        return JobDetails()

    tree = ET.parse(job_xml_path)
    root = tree.getroot()

    panel = root.find(".//Panels/Panel0")
    width_mm = points_to_mm(safe_text(panel.find("XMax")) if panel is not None else None)
    height_mm = points_to_mm(safe_text(panel.find("YMax")) if panel is not None else None)

    return JobDetails(
        customer=safe_text(root.find("./Userinfo/Customer"), "Unknown"),
        submitted_by=safe_text(root.find("./Userinfo/SubmittedBy"), "Unknown"),
        quantity=safe_text(root.find("./Userinfo/Quantity"), "1"),
        note=safe_text(root.find("./Userinfo/Note"), "None"),
        width_mm=width_mm,
        height_mm=height_mm,
    )


def build_output_xml(source_root: ET.Element, settings: Settings) -> tuple[ET.ElementTree, str]:
    pdf_destination = safe_text(source_root.find("PDFDestinationFile"))
    if not pdf_destination:
        raise ValueError("Missing <PDFDestinationFile> tag.")

    unique_code = extract_unique_code(pdf_destination)
    if not unique_code:
        raise ValueError("Could not find a 10-digit unique code in <PDFDestinationFile>.")

    media = None
    matching_cut_queue_xml = get_matching_cut_queue_xml(settings.cut_queue_folder, unique_code)
    if matching_cut_queue_xml is not None:
        media = extract_media(matching_cut_queue_xml)

    output_width_mm = points_to_mm(safe_text(source_root.find("XSize")))
    output_height_mm = points_to_mm(safe_text(source_root.find("YSize")))
    job_count = safe_int(source_root.find(".//JobCnt"))
    copies = safe_text(source_root.find(".//Copies"), "1")
    aggregated_jobs = extract_job_counts(source_root, job_count)

    new_root = ET.Element("NESTINGDESCRIPTIONFILE")
    ET.SubElement(new_root, "NestRef").text = unique_code

    if media:
        ET.SubElement(new_root, "Media").text = media

    ET.SubElement(new_root, "JobCnt").text = str(job_count)
    ET.SubElement(new_root, "Copies").text = copies
    ET.SubElement(new_root, "Width").text = str(output_width_mm)
    ET.SubElement(new_root, "Height").text = str(output_height_mm)

    jobs_element = ET.SubElement(new_root, "Jobs")
    for index, job_data in enumerate(aggregated_jobs.values()):
        job_details = load_job_details(settings.out_folder, job_data["filename"])

        job_element = ET.SubElement(jobs_element, f"Job{index}")
        ET.SubElement(job_element, "JobRef").text = job_data["job_ref"]
        ET.SubElement(job_element, "Filename").text = job_data["filename"]
        ET.SubElement(job_element, "PlacedCopies").text = str(job_data["placed_copies"])
        ET.SubElement(job_element, "Customer").text = job_details.customer
        ET.SubElement(job_element, "SubmittedBy").text = job_details.submitted_by
        ET.SubElement(job_element, "Quantity").text = job_details.quantity
        ET.SubElement(job_element, "Note").text = job_details.note
        ET.SubElement(job_element, "Width").text = str(job_details.width_mm)
        ET.SubElement(job_element, "Height").text = str(job_details.height_mm)

    return ET.ElementTree(new_root), unique_code


def process_xml_file(file_path: Path, settings: Settings) -> Path:
    tree = ET.parse(file_path)
    output_tree, unique_code = build_output_xml(tree.getroot(), settings)

    settings.save_folder.mkdir(parents=True, exist_ok=True)
    output_path = settings.save_folder / f"{unique_code}.xml"
    output_tree.write(output_path, encoding="UTF-8", xml_declaration=True)
    return output_path


class SpecificXMLHandler(FileSystemEventHandler):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def on_modified(self, event) -> None:
        if event.is_directory:
            return

        source_path = Path(event.src_path)
        if source_path.name != self.settings.specific_file:
            return

        logging.info("Detected change in %s", source_path)
        # Small delay to avoid reading the file while it's still being written
        time.sleep(0.5)
        try:
            output_path = process_xml_file(source_path, self.settings)
            logging.info("Generated XML: %s", output_path)
        except Exception as exc:
            logging.exception("Failed to process %s: %s", source_path, exc)


def monitor_folder(settings: Settings) -> None:
    event_handler = SpecificXMLHandler(settings)
    observer = Observer()
    observer.schedule(event_handler, str(settings.folder_to_monitor), recursive=False)
    observer.start()
    logging.info(
        "Monitoring %s for %s",
        settings.folder_to_monitor,
        settings.specific_file,
    )

    try:
        while True:
            time.sleep(settings.poll_interval_seconds)
    except KeyboardInterrupt:
        logging.info("Stopping monitor...")
        observer.stop()

    observer.join()


def main() -> None:
    set_console_title("Prepit XML Builder")
    configure_logging()
    settings = Settings.from_env()
    monitor_folder(settings)


if __name__ == "__main__":
    main()
