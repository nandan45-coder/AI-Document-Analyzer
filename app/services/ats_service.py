ROLE_SKILLS = {

    "Machine Learning Engineer": [
        "python","tensorflow","pytorch","machine learning",
        "deep learning","numpy","pandas","opencv",
        "scikit-learn","nlp","computer vision","cnn"
    ],

    "Data Scientist": [
        "python","machine learning","statistics",
        "pandas","numpy","power bi",
        "tableau","sql","predictive modeling"
    ],

    "Data Analyst": [
        "excel","power bi","sql",
        "tableau","python","statistics",
        "dashboard","reporting"
    ],

    "Business Analyst": [
        "excel","sql","power bi",
        "requirements gathering",
        "stakeholder management",
        "business intelligence"
    ],

    "Software Developer": [
        "python","java","c++",
        "git","github",
        "data structures",
        "algorithms","sql"
    ],

    "Backend Developer": [
        "python","fastapi","django",
        "flask","mongodb",
        "sql","docker",
        "rest api","microservices"
    ],

    "Frontend Developer": [
        "html","css","javascript",
        "react","typescript",
        "nextjs","redux",
        "tailwind"
    ],

    "Full Stack Developer": [
        "html","css","javascript",
        "react","node.js",
        "mongodb","sql",
        "express","docker"
    ],

    "DevOps Engineer": [
        "docker","kubernetes",
        "jenkins","aws",
        "linux","terraform",
        "ci/cd"
    ],

    "Cloud Engineer": [
        "aws","azure","gcp",
        "docker","kubernetes",
        "linux","terraform"
    ],

    "Cyber Security Analyst": [
        "ethical hacking",
        "network security",
        "penetration testing",
        "wireshark",
        "siem","firewall"
    ],

    "AI Engineer": [
        "python","machine learning",
        "deep learning",
        "llm",
        "prompt engineering",
        "langchain",
        "rag",
        "vector database"
    ],

    "Generative AI Engineer": [
        "llm",
        "prompt engineering",
        "langchain",
        "rag",
        "gemini",
        "openai",
        "huggingface",
        "agents"
    ],

    "Mobile App Developer": [
        "android","kotlin",
        "java","flutter",
        "react native","firebase"
    ],

    "QA Engineer": [
        "manual testing",
        "automation testing",
        "selenium",
        "jira",
        "api testing"
    ],

    "Database Administrator": [
        "mysql","postgresql",
        "oracle","sql",
        "backup","recovery"
    ],

    "UI UX Designer": [
        "figma",
        "wireframing",
        "prototyping",
        "user research",
        "design thinking"
    ],

    "Digital Marketing Specialist": [
        "seo","sem",
        "google analytics",
        "social media marketing",
        "content marketing"
    ],

    "Sales Executive": [
        "crm",
        "lead generation",
        "negotiation",
        "sales strategy"
    ],

    "Human Resources": [
        "recruitment",
        "talent acquisition",
        "employee engagement",
        "hr policies"
    ],

    "Data Engineer": [
        "python","sql",
        "etl","spark",
        "hadoop","airflow"
    ],

    "Product Manager": [
        "agile","scrum",
        "product roadmap",
        "stakeholder management"
    ],

    "Project Manager": [
        "project planning",
        "risk management",
        "jira",
        "agile"
    ],

    "Blockchain Developer": [
        "solidity",
        "ethereum",
        "smart contracts",
        "web3"
    ],

    "Game Developer": [
        "unity",
        "unreal engine",
        "c#",
        "game development"
    ],

    "Embedded Engineer": [
        "c","c++",
        "arduino",
        "raspberry pi",
        "microcontroller"
    ],

    "Network Engineer": [
        "routing",
        "switching",
        "tcp/ip",
        "network security"
    ],

    "System Administrator": [
        "linux",
        "windows server",
        "backup",
        "virtualization"
    ],

    "Financial Analyst": [
        "excel",
        "forecasting",
        "financial modeling",
        "budgeting"
    ],

    "Operations Manager": [
        "operations management",
        "leadership",
        "process improvement",
        "supply chain"
    ]
}


def role_based_ats(text, role):

    skills = ROLE_SKILLS.get(role)

    if not skills:
        return {
            "error": "Invalid Role",
            "available_roles": list(
                ROLE_SKILLS.keys()
            )
        }

    text = text.lower()

    matched = []
    missing = []

    for skill in skills:

        if skill.lower() in text:
            matched.append(skill)
        else:
            missing.append(skill)

    score = round(
        (len(matched) / len(skills)) * 100,
        2
    )

    return {
        "role": role,
        "ats_score": score,
        "matched_skills": matched,
        "missing_skills": missing
    }