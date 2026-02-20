Create a new Databricks Unity Catalog schema with external location and grants in the `data_unity_live` environment.

Ask the user for: **schema name**, **Jira ticket** (optional), and **comment** (optional).

---

## Files to modify

1. `environments/data_unity_live/uc-external-locations.tf`
2. `environments/data_unity_live/uc-schemas.tf`
3. `environments/data_unity_live/uc-grants.tf`

---

## 1. External Location

Append to the end of `uc-external-locations.tf`:

```hcl
resource "databricks_external_location" "ext_loc_atvi_data_db_<schema_name>" {
  url             = "gs://atvi-data-db-unity-<schema-name-hyphenated>/"
  owner           = "databricks-terraform@activision.com"
  name            = "ext-loc-atvi-data-<schema-name-hyphenated>"
  credential_name = databricks_storage_credential.unity_storage_credential.name
  comment         = "<comment>"
}
```

Rules:
- Resource label uses underscores: `ext_loc_atvi_data_db_<schema_name>`
- `url` and `name` use hyphens: `<schema-name-hyphenated>`
- `comment` = "For <Schema Name>" or user-provided description, optionally appended with `, <JIRA-TICKET>`

---

## 2. Schema

Append to the end of `uc-schemas.tf`:

```hcl
resource "databricks_schema" "main_<schema_name>" {
  storage_root = databricks_external_location.ext_loc_atvi_data_db_<schema_name>.url
  properties = {
    owner = "root"
  }
  owner        = "databricks-terraform@activision.com"
  name         = "<schema_name>"
  comment      = "<comment>"
  catalog_name = databricks_catalog.main_atvi_uc_metastore_managed_catalog.id
  depends_on   = [databricks_grants.catalog_main]
}
```

---

## 3. Grants (basic)

Append to the end of `uc-grants.tf`:

```hcl
resource "databricks_grants" "schema_main_<schema_name>" {
  schema = databricks_schema.main_<schema_name>.id
  grant {
    privileges = ["USE_SCHEMA", "SELECT"]
    principal  = "dbx-grp-ap"
  }
  grant {
    privileges = ["MODIFY", "CREATE_TABLE", "READ_VOLUME", "WRITE_VOLUME"]
    principal  = "dbx-grp-dw-data-frameworks"
  }
}
```

---

## Common Rules
- Always append to the end of each file.
- `owner` is always `databricks-terraform@activision.com`.
- `credential_name` is always `databricks_storage_credential.unity_storage_credential.name`.
- If the user provides a Jira ticket, append it to the comment: `"For <Schema Name>, <JIRA-TICKET>"`.
- After all 3 files are updated, summarize the changes and ask if the user wants to commit.
