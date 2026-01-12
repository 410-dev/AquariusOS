rootProject.name = "domain-controller-server"

include("lib:libcodablejdbc")
findProject("lib:libcodablejdbc")?.name = "libcodablejdbc"
include("lib:libcodablejson")
findProject("lib:libcodablejson")?.name = "libcodablejson"
