## Reprobuild project file for `test-certificates-spec`.
##
## The test-certificates specification. Consumers (codetracer's CI checks the
## specification beside its implementation) read a checkout at
## `../test-certificates-spec`.
##
## This recipe builds nothing and declares only its package: that is what
## lets a consumer name it in `uses:` (by its directory name,
## `"test-certificates-spec"`) and lets `repro lock refresh` pin it in the
## consumer's `repro.lock`, which is the one record of a repo's dependencies.
## It declares no `uses:` of its own.

import repro_project_dsl

package test_certificates_spec:
  defaultToolProvisioning "path"
