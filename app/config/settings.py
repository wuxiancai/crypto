from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="paper")
    execution_mode: str = Field(default="paper")
    database_url: str = Field(default="postgresql+psycopg://user:pass@localhost:5432/crypto_quant")
    binance_base_url: str = Field(default="https://fapi.binance.com")
    live_trading_confirm: str | None = Field(default=None, alias="LIVE_TRADING_CONFIRM")
    symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT")

    @model_validator(mode="after")
    def reject_live_without_confirmation(self) -> "Settings":
        is_live = self.environment.lower() == "live" or self.execution_mode.lower() == "live"
        if is_live and self.live_trading_confirm != "I_UNDERSTAND_THE_RISK":
            raise ValueError("LIVE_TRADING_CONFIRM=I_UNDERSTAND_THE_RISK is required for live mode")
        return self

