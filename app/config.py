from __future__ import annotations
import json, os
from pathlib import Path
from pydantic import BaseModel, Field, HttpUrl, field_validator

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"

class QuasarConfig(BaseModel):
    argus_url: str = "http://localhost:8000"
    tracked_satellites: list[str] = Field(default_factory=lambda:["ISS (ZARYA)","NOAA 19","NOAA 18"])
    station_id: str = "default"
    collection_interval_s: int = Field(default=30, ge=5, le=3600)
    auto_report_hours: int = Field(default=24, ge=1, le=720)
    stale_after_s: int = Field(default=120, ge=10, le=86400)
    raw_retention_days: int = Field(default=30, ge=1, le=3650)
    incident_retention_days: int = Field(default=3650, ge=30, le=36500)
    dark_vessel_minutes: int = Field(default=15, ge=1, le=1440)
    debris_elevation_threshold_deg: float = Field(default=20.0, ge=-90, le=90)
    anomaly_cooldown_s: int = Field(default=300, ge=0, le=86400)
    max_task_retries: int = Field(default=5, ge=0, le=50)
    notify_severities: list[str] = Field(default_factory=lambda:["CRITICAL","WARNING"])
    cors_origins: list[str] = Field(default_factory=lambda:["http://localhost:8001","http://127.0.0.1:8001"])

    @field_validator('notify_severities')
    @classmethod
    def norm_sev(cls,v): return [str(x).upper() for x in v]

DEFAULTS = QuasarConfig()

def load_config() -> QuasarConfig:
    data={}
    if CONFIG_FILE.exists():
        try: data=json.loads(CONFIG_FILE.read_text())
        except Exception: data={}
    env_map={
        'QUASAR_ARGUS_URL':'argus_url','QUASAR_STATION_ID':'station_id',
        'QUASAR_COLLECTION_INTERVAL_S':'collection_interval_s','QUASAR_STALE_AFTER_S':'stale_after_s',
        'QUASAR_RAW_RETENTION_DAYS':'raw_retention_days','QUASAR_ANOMALY_COOLDOWN_S':'anomaly_cooldown_s'
    }
    for ek,k in env_map.items():
        if os.getenv(ek) is not None: data[k]=os.getenv(ek)
    if os.getenv('QUASAR_CORS_ORIGINS'):
        data['cors_origins']=[x.strip() for x in os.getenv('QUASAR_CORS_ORIGINS','').split(',') if x.strip()]
    return QuasarConfig.model_validate(data)

def save_config(cfg: QuasarConfig) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(cfg.model_dump_json(indent=2))
