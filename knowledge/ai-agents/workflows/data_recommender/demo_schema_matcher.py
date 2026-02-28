"""
Quick demo of schema_matcher utilities.

Shows all functions in action with a sample schema.
"""

from app.workflows.data_recommender.agent import (
    GraphSchema,
    EntityType,
    PropertyInfo,
    RelationshipType,
)
from app.workflows.data_recommender.models import (
    EntityFilter,
    FilterOperator,
)
from app.workflows.data_recommender.schema_matcher import (
    find_entity,
    find_field,
    infer_relationships,
    get_entity_properties,
    validate_filter,
    get_all_entity_names,
    get_all_relationship_types,
)


def create_demo_schema() -> GraphSchema:
    """Create a sample PBM schema."""
    return GraphSchema(
        entities=[
            EntityType(
                name="Patient",
                properties=[
                    PropertyInfo(name="patientId", type="string"),
                    PropertyInfo(name="name", type="string"),
                    PropertyInfo(name="dateOfBirth", type="date"),
                    PropertyInfo(name="chronicConditions", type="string"),
                ]
            ),
            EntityType(
                name="Claim",
                properties=[
                    PropertyInfo(name="claimId", type="string"),
                    PropertyInfo(name="submittedDate", type="date"),
                    PropertyInfo(name="paidAmount", type="number"),
                    PropertyInfo(name="status", type="string"),
                ]
            ),
            EntityType(
                name="Pharmacy",
                properties=[
                    PropertyInfo(name="pharmacyId", type="string"),
                    PropertyInfo(name="name", type="string"),
                    PropertyInfo(name="networkStatus", type="string"),
                ]
            ),
        ],
        relationships=[
            RelationshipType(
                name="FILED_BY",
                from_entity="Claim",
                to_entity="Patient"
            ),
            RelationshipType(
                name="FILLED_AT",
                from_entity="Claim",
                to_entity="Pharmacy"
            ),
        ]
    )


def main():
    """Run the demo."""
    schema = create_demo_schema()

    print("=" * 70)
    print("Schema Matcher Utilities - Demo")
    print("=" * 70)

    # 1. Find entity
    print("\n1. find_entity() - Fuzzy entity matching")
    print("-" * 70)

    print("  find_entity('patients', schema):")
    result = find_entity("patients", schema)
    print(f"    → {result.name if result else 'None'}")

    print("  find_entity('CLAIM', schema):")
    result = find_entity("CLAIM", schema)
    print(f"    → {result.name if result else 'None'}")

    print("  find_entity('pharm', schema):")
    result = find_entity("pharm", schema)
    print(f"    → {result.name if result else 'None'}")

    # 2. Find field
    print("\n2. find_field() - Property name matching")
    print("-" * 70)

    print("  find_field('Patient', 'date of birth', schema):")
    result = find_field("Patient", "date of birth", schema)
    print(f"    → {result}")

    print("  find_field('Claim', 'paid_amount', schema):")
    result = find_field("Claim", "paid_amount", schema)
    print(f"    → {result}")

    print("  find_field('Pharmacy', 'network status', schema):")
    result = find_field("Pharmacy", "network status", schema)
    print(f"    → {result}")

    # 3. Infer relationships
    print("\n3. infer_relationships() - Find connecting relationships")
    print("-" * 70)

    print("  infer_relationships(['Patient', 'Claim'], schema):")
    paths = infer_relationships(["Patient", "Claim"], schema)
    for path in paths:
        print(f"    → {path.from_entity} --[{path.relationship_type}]--> {path.to_entity}")

    print("  infer_relationships(['Patient', 'Claim', 'Pharmacy'], schema):")
    paths = infer_relationships(["Patient", "Claim", "Pharmacy"], schema)
    for path in paths:
        print(f"    → {path.from_entity} --[{path.relationship_type}]--> {path.to_entity}")

    # 4. Get entity properties
    print("\n4. get_entity_properties() - List all properties")
    print("-" * 70)

    print("  get_entity_properties('Claim', schema):")
    props = get_entity_properties("Claim", schema)
    for prop in props:
        print(f"    → {prop.name}: {prop.type}")

    # 5. Validate filter
    print("\n5. validate_filter() - Filter validation")
    print("-" * 70)

    # Valid filter
    filter1 = EntityFilter(
        property="paidAmount",
        operator=FilterOperator.GT,
        value=1000
    )
    print(f"  Filter: paidAmount > 1000")
    errors = validate_filter(filter1, "Claim", schema)
    print(f"    → {'✓ Valid' if not errors else f'✗ Errors: {errors}'}")

    # Invalid property
    filter2 = EntityFilter(
        property="unknownField",
        operator=FilterOperator.EQ,
        value="test"
    )
    print(f"  Filter: unknownField = 'test'")
    errors = validate_filter(filter2, "Claim", schema)
    print(f"    → {'✓ Valid' if not errors else f'✗ Error: {errors[0]}'}")

    # Invalid operator for type
    filter3 = EntityFilter(
        property="status",
        operator=FilterOperator.GT,
        value="approved"
    )
    print(f"  Filter: status > 'approved'")
    errors = validate_filter(filter3, "Claim", schema)
    print(f"    → {'✓ Valid' if not errors else f'✗ Error: {errors[0]}'}")

    # 6. Utility functions
    print("\n6. Utility Functions")
    print("-" * 70)

    print("  get_all_entity_names(schema):")
    names = get_all_entity_names(schema)
    print(f"    → {', '.join(names)}")

    print("  get_all_relationship_types(schema):")
    types = get_all_relationship_types(schema)
    print(f"    → {', '.join(types)}")

    print("\n" + "=" * 70)
    print("Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
