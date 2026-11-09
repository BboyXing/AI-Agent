from pydantic import BaseModel, ConfigDict


class IdentityContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject: str
    key_id: str
