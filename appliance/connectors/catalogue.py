"""The universal connector catalogue.

Every category the appliance is designed to integrate with. Exactly one has an
adapter implemented today.

A catalogue entry with no adapter reports NOT_CONFIGURED with
`adapter_implemented: False`. That is deliberately distinguishable from DISABLED:
conflating them would overstate capability, and a technical reviewer will ask.
"""
from __future__ import annotations

# (connector_id, display name, category, adapter_implemented)
CATALOGUE: tuple[tuple[str, str, str, bool], ...] = (
    # Product lifecycle
    ("PLM", "PLM / PDM", "Product lifecycle", False),
    ("CAD", "CAD / Design", "Product lifecycle", False),
    ("BOM", "BOM / Product Structure", "Product lifecycle", False),
    ("ECM", "Engineering Change Management", "Product lifecycle", False),
    ("CONFIG_MGMT", "Configuration Management", "Product lifecycle", False),
    ("DIGITAL_THREAD", "Digital Thread", "Product lifecycle", False),
    # Requirements and software lifecycle
    ("ALM", "ALM / Requirements", "Requirements and software", False),
    ("REQUIREMENTS", "Requirements Management", "Requirements and software", False),
    ("MBSE", "MBSE / Architecture", "Requirements and software", False),
    ("SOURCE_CONTROL", "Source Control", "Requirements and software", False),
    ("ISSUE_MGMT", "Issue / Work Management", "Requirements and software", False),
    ("CICD", "CI/CD", "Requirements and software", False),
    # Quality
    ("QMS", "QMS / Quality", "Quality", False),
    ("FMEA_SYS", "FMEA System", "Quality", False),
    ("APQP", "APQP", "Quality", False),
    ("PPAP", "PPAP", "Quality", False),
    ("CONTROL_PLAN", "Control Plan", "Quality", False),
    ("CAR_SCAR", "8D / CAR / SCAR", "Quality", False),
    ("NCR", "NCR / Nonconformance", "Quality", False),
    ("AUDIT", "Audit", "Quality", False),
    ("SPC", "SPC", "Quality", False),
    ("MSA", "MSA", "Quality", False),
    # Verification and validation
    ("TEST_MGMT", "Test Management", "Verification and validation", False),
    ("DVPR", "DVP&R", "Verification and validation", False),
    ("TEST_RESULTS", "Test Results", "Verification and validation", False),
    ("HIL_SIL", "HIL / SIL / MIL", "Verification and validation", False),
    ("CAE", "Simulation / CAE", "Verification and validation", False),
    ("CALIBRATION", "Calibration", "Verification and validation", False),
    ("DIAGNOSTICS", "Vehicle Diagnostics", "Verification and validation", False),
    ("MEASUREMENT", "Measurement Data", "Verification and validation", False),
    # Vehicle and field
    ("TELEMETRY", "Vehicle Telemetry", "Vehicle and field", False),
    ("IOT", "IoT / Edge", "Vehicle and field", False),
    ("VEHICLE_NET", "CAN / LIN / Vehicle Networks", "Vehicle and field", False),
    ("WARRANTY", "Warranty", "Vehicle and field", False),
    ("FIELD_QUALITY", "Field Quality", "Vehicle and field", False),
    ("COMPLAINTS", "Customer Complaints", "Vehicle and field", False),
    ("SERVICE", "Service / After-sales", "Vehicle and field", False),
    # Manufacturing and supply chain
    ("MES", "MES", "Manufacturing and supply chain", False),
    ("ERP", "ERP", "Manufacturing and supply chain", False),
    ("SRM", "Supplier Management", "Manufacturing and supply chain", False),
    ("SUPPLIER_QUALITY", "Supplier Quality", "Manufacturing and supply chain", False),
    ("PROCUREMENT", "Procurement", "Manufacturing and supply chain", False),
    ("SCADA", "SCADA / Industrial IoT", "Manufacturing and supply chain", False),
    # Enterprise information
    ("DATA_LAKE", "Data Lake / Warehouse", "Enterprise information", False),
    ("OBJECT_STORAGE", "Object Storage", "Enterprise information", False),
    ("DMS", "Document Management", "Enterprise information", False),
    ("KNOWLEDGE_BASE", "Knowledge Base / Wiki", "Enterprise information", False),
    ("FILESYSTEM", "File Systems", "Enterprise information", False),
    ("COLLABORATION", "Collaboration", "Enterprise information", False),
    ("EMAIL", "Email", "Enterprise information", False),
    ("PROJECT_MGMT", "Project Management", "Enterprise information", False),
    # External and knowledge
    ("STANDARDS", "Standards / Regulatory", "External and knowledge", False),
    ("CUSTOMER_SPECS", "OEM / Customer Specifications", "External and knowledge", False),
    ("LITERATURE", "Technical Literature", "External and knowledge", False),
    ("PUBLIC_WEB", "Public Web Intelligence", "External and knowledge", False),
    ("PUBLIC_DATA", "Public Datasets", "External and knowledge", False),
    # The one adapter implemented today, over two synthetic datasets
    ("SIMULATION", "Simulation / Public Data", "Simulation", True),
    ("FIRE_SIMULATION", "Fire Engineering Simulation (synthetic public demonstrator)",
     "Simulation", True),
)


def catalogue_rows() -> list[dict]:
    return [{"connector_id": cid, "name": name, "category": cat,
             "adapter_implemented": impl}
            for cid, name, cat, impl in CATALOGUE]


def by_category() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in catalogue_rows():
        grouped.setdefault(row["category"], []).append(row)
    return grouped
