"""Strict, local development-template format; no Gold, credentials or arbitrary extensions."""
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StrictBool

from contracts.models import Cents, Count, Id, Message, Policy, Text, Wire


class TemplateItem(Wire):
    item_id: Id
    name: Text
    quantity: Count
    gross_cents: Cents
    allocated_paid_cents: Cents
    eligible: StrictBool


class TemplateOrder(Wire):
    order_id: Id
    paid_cents: Cents
    items: Annotated[list[TemplateItem], Field(min_length=1, max_length=30)]


class DevelopmentFixture(Wire):
    fixture_schema_version: Literal[1]
    fixture_id: Id
    fixture_version: Id
    source_case_id: Id
    parent_case_id: Id | None
    family_id: Id
    fixture_source: Literal["development_only"]
    review_status: Literal["pending_A_C_D_review"]
    notice: Text
    business_time: AwareDatetime
    customer_id: Id
    request: Text
    candidate_order_ids: Annotated[list[Id], Field(min_length=1, max_length=30)]
    orders: Annotated[list[TemplateOrder], Field(min_length=1, max_length=30)]
    messages: Annotated[list[Message], Field(max_length=30)]
    policy: Policy
    merchant_balance_cents: Cents
    customer_balance_cents: Literal[0]
