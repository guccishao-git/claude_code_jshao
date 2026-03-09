Generate Terraform resource blocks for new Databricks users, service principals, groups, or group memberships.

Ask the user what they need to create: a **user**, a **service principal**, a **group**, a **group membership**, or any combination.

## Step 1: Check for existing user

Before generating any resource block, if a user (email) is being created, search `/Users/jason.shao/Documents/GitHub1/databricks-terraform/account/users.tf` for the provided email address.

- If the email is **already present** in the file, stop immediately and inform the user that the email already exists in `users.tf`. Do not generate any resource block.
- If the email is **not found**, proceed with generating the resource block.

## Step 2: Insert into users.tf

After generating a user resource block, append it to the bottom of `/Users/jason.shao/Documents/GitHub1/databricks-terraform/account/users.tf`. Add a blank line before the new block if the file does not already end with one.

---

## User

The user will provide: full name and email address.

Template:

```hcl
resource "databricks_user" "<short_name>" {
  provider     = databricks.accounts
  user_name    = "<email>"
  force        = true
  display_name = "<Full Name>"
}
```

Rules:
- `<short_name>` is derived from the email prefix (the part before `@`), with any dots replaced by underscores. For example, `brett.garcia@activision.com` becomes `brett_garcia`, `jshao@demonware.net` becomes `jshao`.
- `<email>` is the full email address provided.
- `<Full Name>` is the display name in Title Case (e.g. `Jason Shao`, `Brett Garcia`).

---

## Service Principal

The user will provide: a display name for the service principal.

Template:

```hcl
resource "databricks_service_principal" "<resource_name>" {
  provider     = databricks.accounts
  force        = true
  display_name = "<display_name>"
}
```

Rules:
- `<resource_name>` is the display name with hyphens replaced by underscores. For example, `dbx-sp-dw-client-code` becomes `dbx_sp_dw_client_code`.
- `<display_name>` is the display name exactly as provided by the user.
- Before generating, search `/Users/jason.shao/Documents/GitHub1/databricks-terraform/account/users.tf` for the display name. If it is already present, stop and inform the user. Do not generate any resource block.
- After generating the resource block, append it to the bottom of `/Users/jason.shao/Documents/GitHub1/databricks-terraform/account/users.tf`. Add a blank line before the new block if the file does not already end with one.

---

## Group

The user will provide: a display name for the group.

Template:

```hcl
resource "databricks_group" "<resource_name>" {
  provider     = databricks.accounts
  force        = true
  display_name = "<display_name>"
}
```

Rules:
- `<resource_name>` is the display name with hyphens replaced by underscores. For example, `dbx-grp-ap` becomes `dbx_grp_ap`.
- `<display_name>` is the display name exactly as provided by the user.

After generating the group resource block, append it to the bottom of `/Users/jason.shao/Documents/GitHub1/databricks-terraform/account/groups.tf`. Add a blank line before the new block if the file does not already end with one.

---

## Group Membership

The user will provide: the user's email (or resource name) and the target group name.

Steps:
1. Search `groups.tf` for the group by display name to find its resource name (e.g. `dbx_grp_ap_ga_mobile_analytics_895627063053848`).
2. Derive the `member_id` from `databricks_user.<short_name>.id` where `<short_name>` is the email prefix with dots removed.
3. Generate the resource block and append it to the bottom of `/Users/jason.shao/Documents/GitHub1/databricks-terraform/account/groups.tf`.

Template:

```hcl
resource "databricks_group_member" "<group_resource_name>_<short_name>" {
  provider  = databricks.accounts
  member_id = databricks_user.<short_name>.id
  group_id  = databricks_group.<group_resource_name>.id
}
```

Rules:
- `<group_resource_name>` is the full Terraform resource name of the group found in `groups.tf`.
- `<short_name>` is derived from the email prefix with dots removed (e.g. `brett.garcia` → `brett_garcia` for the resource suffix, `brettgarcia` for the member_id reference).
- Add a blank line before the new block if the file does not already end with one.

---

## Common Rules
- Always use `provider = databricks.accounts`.
- Always set `force = true`.
- Output only the resource block(s), no extra explanation.
- If the user provides multiple entries, generate one resource block per entry.
