from pydantic import BaseModel


class JDMatchRequest(BaseModel):
    job_description: str