"""Behavioral boundaries for the national 2026 trade-in estimates."""

import importlib

import pytest


def calculate(name, inputs, **kwargs):
    module = importlib.import_module("app.agents.dsl_generator.trade_in_calculations")
    return getattr(module, name)(inputs, **kwargs)


def product_inputs(**changes):
    inputs = {
        "price": 3999.99,
        "category": "refrigerator",
        "energy_level": 1,
        "claim_time": "2026-11-21",
        "purchase_date": "2026-11-20",
        "invoice_date": "2026-11-20",
        "individual_consumer": True,
        "participating_merchant": True,
        "new_product": True,
        "identity_consistent": True,
        "real_name_single_item_invoice": True,
        "prior_category_claims": 0,
    }
    inputs.update(changes)
    return inputs


def car_inputs(**changes):
    inputs = {
        "price": 100000,
        "claim_time": "2026-11-21",
        "old_fuel": "gasoline",
        "old_registration_date": "2013-06-30",
        "old_owned_since": "2025-01-08",
        "new_fuel": "nev",
        "nev_in_catalog": True,
        "individual_consumer": True,
        "old_passenger_car": True,
        "new_passenger_car": True,
        "same_owner": True,
        "new_owned_during_review": True,
        "same_province": True,
        "documents_valid": True,
        "prior_auto_claims": 0,
        "qualified_scrapper": True,
        "scrap_certificate_date": "2026-01-01",
        "scrap_delivery_date": "2026-01-01",
        "deregistration_date": "2026-01-02",
        "deregistration_certificate_date": "2026-01-02",
        "transfer_invoice_date": "2026-01-01",
        "transfer_registration_date": "2026-01-02",
        "new_invoice_date": "2026-01-01",
        "new_registration_date": "2026-01-02",
    }
    inputs.update(changes)
    return inputs


@pytest.mark.parametrize("price,amount", [(1000, 150), (3999.99, 600), (10000, 1500), (20000, 1500)])
def test_appliance_rates_caps_and_cent_display(price, amount):
    result = calculate("appliance_subsidy_2026", product_inputs(price=price))
    assert result["status"] == "CALCULATED"
    assert result["amount"] == amount
    assert isinstance(result["amount"], float)


@pytest.mark.parametrize("category", ["refrigerator", "washing_machine", "tv", "air_conditioner", "water_heater", "computer"])
def test_all_six_appliance_categories(category):
    assert calculate("appliance_subsidy_2026", product_inputs(category=category))["status"] == "CALCULATED"


@pytest.mark.parametrize("price,amount", [(1000, 150), (3333.33, 500), (6000, 500)])
@pytest.mark.parametrize("category", ["phone", "tablet", "smart_watch_band", "smart_glasses"])
def test_digital_categories_price_boundary_and_cap(price, amount, category):
    result = calculate("digital_subsidy_2026", product_inputs(price=price, category=category))
    assert (result["status"], result["amount"]) == ("CALCULATED", amount)


@pytest.mark.parametrize("changes", [{"category": "dryer"}, {"energy_level": 2}, {"prior_category_claims": 1}, {"individual_consumer": False}, {"participating_merchant": False}, {"new_product": False}, {"identity_consistent": False}, {"real_name_single_item_invoice": False}, {"purchase_date": "2025-12-31"}, {"invoice_date": "2025-12-31"}, {"claim_time": "2027-01-01"}])
def test_ineligible_appliance_never_pays(changes):
    result = calculate("appliance_subsidy_2026", product_inputs(**changes))
    assert result["status"] == "INELIGIBLE"
    assert result["amount"] == 0


@pytest.mark.parametrize("changes", [{"price": 6000.01}, {"category": "computer"}, {"prior_category_claims": 1}])
def test_ineligible_digital_never_pays(changes):
    assert calculate("digital_subsidy_2026", product_inputs(category="phone") | changes)["status"] == "INELIGIBLE"


@pytest.mark.parametrize("name,inputs", [("appliance_subsidy_2026", product_inputs()), ("digital_subsidy_2026", product_inputs(category="phone")), ("auto_trade_in_2026", car_inputs())])
@pytest.mark.parametrize("price", [None, 0, -1, True, float("nan"), float("inf"), "not a number"])
def test_invalid_price_never_pays(name, inputs, price):
    result = calculate(name, inputs | {"price": price})
    assert result["status"] == "INVALID_INPUT"
    assert result["amount"] == 0


@pytest.mark.parametrize("field", list(product_inputs()))
def test_each_appliance_fact_is_required(field):
    inputs = product_inputs()
    del inputs[field]
    assert calculate("appliance_subsidy_2026", inputs)["status"] == "INVALID_INPUT"


@pytest.mark.parametrize("changes", [{"claim_time": "2026-02-30"}, {"invoice_date": "2026-12-01"}, {"purchase_date": "2026-12-01"}, {"prior_category_claims": -1}, {"prior_category_claims": 0.5}, {"individual_consumer": "true"}, {"energy_level": True}])
def test_product_invalid_dates_types_counts(changes):
    assert calculate("appliance_subsidy_2026", product_inputs(**changes))["status"] == "INVALID_INPUT"


@pytest.mark.parametrize("mode,new_fuel,price,amount", [("scrap", "nev", 100000, 12000), ("scrap", "nev", 200000, 20000), ("scrap", "fuel", 200000, 15000), ("replace", "nev", 200000, 15000), ("replace", "fuel", 300000, 13000), ("scrap", "nev", 100000.01, 12001), ("replace", "nev", 100000.01, 8001), ("scrap", "fuel", 100000.01, 10001), ("replace", "fuel", 100000.01, 6001), ("scrap", "nev", 133350, 16002)])
def test_car_rates_caps_and_exact_decimal_ceiling(mode, new_fuel, price, amount):
    result = calculate("auto_trade_in_2026", car_inputs(price=price, new_fuel=new_fuel, displacement_liters=2.0), mode=mode)
    assert (result["status"], result["amount"]) == ("CALCULATED", amount)


@pytest.mark.parametrize("fuel,last_day,next_day", [("gasoline", "2013-06-30", "2013-07-01"), ("diesel", "2015-06-30", "2015-07-01"), ("other", "2015-06-30", "2015-07-01"), ("nev", "2019-12-31", "2020-01-01")])
def test_scrap_registration_thresholds_are_inclusive(fuel, last_day, next_day):
    eligible = car_inputs(old_fuel=fuel, old_registration_date=last_day)
    assert calculate("auto_trade_in_2026", eligible)["status"] == "CALCULATED"
    assert calculate("auto_trade_in_2026", eligible | {"old_registration_date": next_day})["status"] == "INELIGIBLE"


@pytest.mark.parametrize("mode", ["scrap", "replace"])
@pytest.mark.parametrize("changes", [{"old_owned_since": "2025-01-09"}, {"same_owner": False}, {"new_owned_during_review": False}, {"same_province": False}, {"documents_valid": False}, {"old_passenger_car": False}, {"new_passenger_car": False}, {"individual_consumer": False}, {"prior_auto_claims": 1}, {"nev_in_catalog": False}, {"new_fuel": "fuel", "displacement_liters": 2.01}, {"new_invoice_date": "2025-12-31"}, {"new_registration_date": "2025-12-31"}, {"claim_time": "2027-01-01"}])
def test_car_identity_ownership_dates_and_cross_scheme_once(mode, changes):
    result = calculate("auto_trade_in_2026", car_inputs(**changes), mode=mode)
    assert result["status"] == "INELIGIBLE"
    assert result["amount"] == 0


@pytest.mark.parametrize("mode,field", [("scrap", "scrap_certificate_date"), ("scrap", "scrap_delivery_date"), ("scrap", "deregistration_date"), ("scrap", "deregistration_certificate_date"), ("replace", "transfer_invoice_date"), ("replace", "transfer_registration_date")])
def test_each_disposal_document_date_is_checked(mode, field):
    assert calculate("auto_trade_in_2026", car_inputs(**{field: "2025-12-31"}), mode=mode)["status"] == "INELIGIBLE"
    inputs = car_inputs()
    del inputs[field]
    assert calculate("auto_trade_in_2026", inputs, mode=mode)["status"] == "INVALID_INPUT"


@pytest.mark.parametrize("field", ["price", "claim_time", "old_fuel", "old_registration_date", "old_owned_since", "new_fuel", "nev_in_catalog", "individual_consumer", "old_passenger_car", "new_passenger_car", "same_owner", "new_owned_during_review", "same_province", "documents_valid", "prior_auto_claims", "qualified_scrapper", "new_invoice_date", "new_registration_date"])
def test_each_scrap_fact_is_required(field):
    inputs = car_inputs()
    del inputs[field]
    assert calculate("auto_trade_in_2026", inputs)["status"] == "INVALID_INPUT"


def test_scrapping_nev_cannot_subsidize_new_fuel_car():
    inputs = car_inputs(old_fuel="nev", old_registration_date="2019-12-31", new_fuel="fuel", displacement_liters=1.5)
    assert calculate("auto_trade_in_2026", inputs)["status"] == "INELIGIBLE"
    assert calculate("auto_trade_in_2026", inputs, mode="replace")["status"] == "CALCULATED"


@pytest.mark.parametrize("changes", [{"new_registration_date": "2026-12-01"}, {"new_invoice_date": "2026-01-03"}, {"old_owned_since": "2010-01-01"}, {"prior_auto_claims": True}, {"claim_time": "bad"}])
def test_car_impossible_or_invalid_facts(changes):
    assert calculate("auto_trade_in_2026", car_inputs(**changes))["status"] == "INVALID_INPUT"


def test_car_does_not_invent_new_car_or_mode_qualifications():
    inputs = car_inputs(new_fuel="fuel")
    assert calculate("auto_trade_in_2026", inputs)["status"] == "INVALID_INPUT"
    assert calculate("auto_trade_in_2026", car_inputs(), mode="unknown")["status"] == "INVALID_INPUT"
    assert calculate("auto_trade_in_2026", car_inputs(qualified_scrapper=False))["status"] == "INELIGIBLE"


@pytest.mark.parametrize("name,inputs,field", [("appliance_subsidy_2026", product_inputs(), "category"), ("digital_subsidy_2026", product_inputs(category="phone"), "category"), ("auto_trade_in_2026", car_inputs(), "old_fuel"), ("auto_trade_in_2026", car_inputs(), "new_fuel")])
@pytest.mark.parametrize("value", [[], {}, True, 42])
def test_malformed_category_inputs_return_validation_result(name, inputs, field, value):
    assert calculate(name, inputs | {field: value})["status"] == "INVALID_INPUT"


@pytest.mark.parametrize("field", [key for key in product_inputs() if key != "energy_level"])
def test_each_digital_fact_is_required(field):
    inputs = product_inputs(category="phone")
    del inputs[field]
    assert calculate("digital_subsidy_2026", inputs)["status"] == "INVALID_INPUT"


@pytest.mark.parametrize("mode", ["scrap", "replace"])
def test_policy_calendar_and_ownership_edges(mode):
    inputs = car_inputs(claim_time="2026-12-31", new_invoice_date="2026-12-31", new_registration_date="2026-12-31")
    assert calculate("auto_trade_in_2026", inputs, mode=mode)["status"] == "CALCULATED"
    assert calculate("auto_trade_in_2026", inputs | {"old_owned_since": "2025-01-09"}, mode=mode)["amount"] == 0


@pytest.mark.parametrize("name,inputs", [("appliance_subsidy_2026", product_inputs()), ("digital_subsidy_2026", product_inputs(category="phone"))])
def test_product_calendar_start_and_end(name, inputs):
    for day in ["2026-01-01", "2026-12-31"]:
        assert calculate(name, inputs | {"claim_time": day, "invoice_date": day, "purchase_date": day})["status"] == "CALCULATED"


@pytest.mark.parametrize("mode,changes", [("scrap", {"scrap_delivery_date": "2026-01-02"}), ("scrap", {"deregistration_certificate_date": "2026-01-01"}), ("replace", {"transfer_invoice_date": "2026-01-03"})])
def test_disposal_proof_cannot_precede_the_transaction(mode, changes):
    assert calculate("auto_trade_in_2026", car_inputs(**changes), mode=mode)["status"] == "INVALID_INPUT"


def test_non_string_mode_returns_validation_result():
    assert calculate("auto_trade_in_2026", car_inputs(), mode=[])["status"] == "INVALID_INPUT"


@pytest.mark.parametrize("name,inputs", [("appliance_subsidy_2026", product_inputs()), ("digital_subsidy_2026", product_inputs(category="phone")), ("auto_trade_in_2026", car_inputs())])
@pytest.mark.parametrize("price", ["1e1000001", "1e-1000001"])
def test_numbers_outside_float_input_range_return_invalid_input(name, inputs, price):
    result = calculate(name, inputs | {"price": price})
    assert result["status"] == "INVALID_INPUT"
    assert result["amount"] == 0
