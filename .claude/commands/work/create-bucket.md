Create a new GCS bucket in the unitystorage-live project and register it for inventory reporting.

## Arguments
- $ARGUMENTS: The bucket name suffix (e.g. "tableau_test" becomes "atvi-data-db-unity-tableau-test")

## Steps

1. **Add the bucket resource** to `/Users/jason.shao/Documents/GitHub/data-terraform/atvi-data-unitystorage-live/buckets.tf`

   Use this template, replacing the name accordingly (hyphens in bucket name, underscores in resource name):

   ```hcl
   resource "google_storage_bucket" "atvi_data_db_unity_<name_with_underscores>" {
     force_destroy               = false
     location                    = "us-west4"
     name                        = "atvi-data-db-unity-<name-with-hyphens>"
     project                     = "atvi-data-unitystorage-live-65"
     public_access_prevention    = "enforced"
     storage_class               = "STANDARD"
     uniform_bucket_level_access = true
     soft_delete_policy {
       retention_duration_seconds = 604800  # 7 days in seconds; default
     }
     versioning {
       enabled = false
     }
     lifecycle_rule {
       action    { type = "Delete" }
       condition { num_newer_versions = 1 }
     }
     lifecycle_rule {
       action    { type = "Delete" }
       condition { days_since_noncurrent_time = 7 }
     }
   }
   ```

2. **Add the bucket to the inventory_reports map** in `/Users/jason.shao/Documents/GitHub/data-terraform/atvi-data-unitystorage-live/inventory.tf`

   Add the entry `"atvi-data-db-unity-<name-with-hyphens>" = {}` to the `local.inventory_reports` block.
