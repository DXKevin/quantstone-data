import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

ID_SEGMENT = re.compile(r"^[a-z][a-z0-9_]*$")


class DatasetStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    DEPRECATED = "deprecated"


class CollectionPurpose(StrEnum):
    INITIAL = "initial"
    INCREMENTAL = "incremental"
    REPAIR = "repair"
    REPLACE = "replace"


class DatasetCollectionBinding(BaseModel):
    purpose: CollectionPurpose
    collector_key: str = Field(min_length=1, max_length=128)
    operation: str = Field(min_length=1, max_length=128)


class DatasetStoragePolicy(BaseModel):
    logical_partition_field: str | None = None
    layout: str = Field(pattern=r"^(daily|yearly_with_delta|snapshot)$")
    write_strategy: str = Field(pattern=r"^(append|replace_partition|replace_snapshot)$")
    compaction: str | None = Field(default=None, pattern=r"^yearly$")


class DatasetFieldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_]*$")
    data_type: str = Field(min_length=1, max_length=64)
    nullable: bool = True
    description: str = Field(min_length=1)
    unit: str | None = Field(default=None, max_length=64)
    source_name: str | None = Field(default=None, max_length=128)


class DatasetCreate(BaseModel):
    id: str = Field(min_length=7, max_length=255)
    provider: str = Field(min_length=1, max_length=64)
    region: str = Field(min_length=1, max_length=32)
    instrument: str = Field(min_length=1, max_length=64)
    dataset_name: str = Field(min_length=1, max_length=128)
    market: str | None = Field(default=None, max_length=32)
    display_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    collection_bindings: list[DatasetCollectionBinding] = Field(default_factory=list)
    storage_policy: DatasetStoragePolicy | None = None
    primary_key: list[str] = Field(min_length=1)
    time_field: str | None = None
    fields: list[DatasetFieldCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_contract(self) -> "DatasetCreate":
        purposes = [binding.purpose for binding in self.collection_bindings]
        if len(purposes) != len(set(purposes)):
            raise ValueError("collection binding purposes must be unique")
        segments = [self.provider, self.region, self.instrument, self.dataset_name]
        if self.market:
            segments.append(self.market)
        for segment in segments:
            if not ID_SEGMENT.fullmatch(segment):
                raise ValueError(f"invalid dataset ID segment: {segment}")
        expected_id = ".".join(segments)
        if self.id != expected_id:
            raise ValueError(f"dataset id must be {expected_id}")

        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("field names must be unique")
        unknown_primary_key = set(self.primary_key) - set(names)
        if unknown_primary_key:
            raise ValueError(f"primary key fields are undefined: {sorted(unknown_primary_key)}")
        if self.time_field and self.time_field not in names:
            raise ValueError(f"time field is undefined: {self.time_field}")
        return self


class DatasetUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    collection_bindings: list[DatasetCollectionBinding] = Field(default_factory=list)
    storage_policy: DatasetStoragePolicy | None = None
    primary_key: list[str] = Field(min_length=1)
    time_field: str | None = None
    fields: list[DatasetFieldCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_contract(self) -> "DatasetUpdate":
        purposes = [binding.purpose for binding in self.collection_bindings]
        if len(purposes) != len(set(purposes)):
            raise ValueError("collection binding purposes must be unique")
        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("field names must be unique")
        unknown_primary_key = set(self.primary_key) - set(names)
        if unknown_primary_key:
            raise ValueError(f"primary key fields are undefined: {sorted(unknown_primary_key)}")
        if self.time_field and self.time_field not in names:
            raise ValueError(f"time field is undefined: {self.time_field}")
        return self


class DatasetFieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    data_type: str
    nullable: bool
    description: str
    unit: str | None
    source_name: str | None
    position: int


class DatasetSchemaRead(BaseModel):
    version: int
    primary_key: list[str]
    time_field: str | None
    created_at: datetime
    fields: list[DatasetFieldRead]


class DatasetRead(BaseModel):
    model_config = ConfigDict(validate_by_name=True)

    id: str
    provider: str
    region: str
    instrument: str
    dataset_name: str
    market: str | None
    display_name: str
    description: str | None
    collection_bindings: list[DatasetCollectionBinding]
    storage_policy: DatasetStoragePolicy | None
    status: DatasetStatus
    current_schema_version: int
    created_at: datetime
    updated_at: datetime
    schema_: DatasetSchemaRead = Field(alias="schema")


class DatasetSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    provider: str
    region: str
    instrument: str
    market: str | None
    status: DatasetStatus
    current_schema_version: int
    collection_bindings: list[DatasetCollectionBinding]
    storage_policy: DatasetStoragePolicy | None
