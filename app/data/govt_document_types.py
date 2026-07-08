"""
Supported Maharashtra Government Documents
Government Document Intelligence Module
"""

GOVT_DOCUMENT_TYPES = {

    "Income Certificate": {

        "aliases": [
            "income certificate",
            "certificate of income",
            "annual income certificate"
        ],

        "fields": [
            "Applicant Name",
            "Father Name",
            "Certificate Number",
            "Issue Date",
            "District",
            "Taluka",
            "Authority"
        ]

    },

    "Domicile Certificate": {

        "aliases": [
            "domicile certificate",
            "residence certificate"
        ],

        "fields": [
            "Applicant Name",
            "Father Name",
            "Nationality",
            "Address",
            "Certificate Number",
            "Issue Date",
            "District",
            "Authority"
        ]

    },

    "Age Nationality Certificate": {

        "aliases": [
            "age nationality",
            "age and nationality certificate"
        ],

        "fields": [
            "Applicant Name",
            "Date of Birth",
            "Nationality",
            "Certificate Number",
            "Issue Date",
            "Authority"
        ]

    },

    "Non Creamy Layer Certificate": {

        "aliases": [
            "non creamy layer",
            "ncl certificate"
        ],

        "fields": [
            "Applicant Name",
            "Category",
            "Certificate Number",
            "Issue Date",
            "District",
            "Authority"
        ]

    },

    "Caste Certificate": {

        "aliases": [
            "caste certificate"
        ],

        "fields": [
            "Applicant Name",
            "Category",
            "Sub Category",
            "Certificate Number",
            "Issue Date",
            "Authority"
        ]

    },

    "Caste Validity Certificate": {

        "aliases": [
            "caste validity",
            "validity certificate"
        ],

        "fields": [
            "Applicant Name",
            "Category",
            "Certificate Number",
            "Issue Date",
            "Validity",
            "Authority"
        ]

    },

    "EWS Certificate": {

        "aliases": [
            "ews",
            "economically weaker section"
        ],

        "fields": [
            "Applicant Name",
            "Certificate Number",
            "Issue Date",
            "Authority"
        ]

    },

    "Birth Certificate": {

        "aliases": [
            "birth certificate"
        ],

        "fields": [
            "Child Name",
            "Date of Birth",
            "Gender",
            "Registration Number",
            "Registration Date"
        ]

    },

    "Death Certificate": {

        "aliases": [
            "death certificate"
        ],

        "fields": [
            "Name",
            "Date of Death",
            "Registration Number",
            "Registration Date"
        ]

    },

    "Marriage Certificate": {

        "aliases": [
            "marriage certificate"
        ],

        "fields": [
            "Bride Name",
            "Groom Name",
            "Marriage Date",
            "Registration Number"
        ]

    },

    "Disability Certificate": {

        "aliases": [
            "disability certificate",
            "pwd certificate"
        ],

        "fields": [
            "Applicant Name",
            "Disability Type",
            "Percentage",
            "Certificate Number",
            "Issue Date"
        ]

    },

    "Senior Citizen Certificate": {

        "aliases": [
            "senior citizen certificate"
        ],

        "fields": [
            "Applicant Name",
            "Age",
            "Certificate Number",
            "Issue Date"
        ]

    }

}


# ==========================================================
# Verification Symbols
# ==========================================================

VERIFICATION_SYMBOLS = {

    "GREEN_TICK": {

        "status": "Verified",

        "ready_for_submission": True

    },

    "YELLOW_QUESTION": {

        "status": "Verification Pending",

        "ready_for_submission": False

    }

}


# ==========================================================
# Supported File Formats
# ==========================================================

SUPPORTED_FILE_TYPES = [

    ".pdf",

    ".png",

    ".jpg",

    ".jpeg"

]


# ==========================================================
# Confidence Thresholds
# ==========================================================

CONFIDENCE_THRESHOLDS = {

    "document_classification": 0.80,

    "verification_symbol": 0.90

}