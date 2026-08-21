#
# Renders `make help` output grouped into sections declared with '##@ Section Name'
# comments. Invoked by scripts/makefiles/help.mk (do not run directly).
#
# Section rules:
# - A '##@ Section Name' line starts (or resumes, if repeated) a section; every
#   'target: ... ## description' line below it (until the next '##@') belongs to it.
# - The same section name in different files accumulates into one section.
# - Targets with no preceding '##@' anywhere in the scanned files fall into a
#   leading, unlabeled section (no header line printed).
# - Sections are printed in first-seen order; targets within a section are
#   sorted alphabetically (requires gawk's asort()).
#

BEGIN {
    FS = ":.*?## "
    section = ""
    n_sections = 0
}

/^##@/ {
    name = $0
    sub(/^##@[ \t]*/, "", name)
    if (!(name in seen_section)) {
        n_sections++
        section_name[n_sections] = name
        seen_section[name] = 1
    }
    section = name
    next
}

/^[[:alnum:][:space:]_-]+:.*?## / {
    if ($1 == "help" || $1 ~ /^hel%/) next
    count[section]++
    key = section SUBSEP count[section]
    target[key] = $1
    desc[target[key] SUBSEP section] = $2
    next
}

END {
    for (s = 0; s <= n_sections; s++) {
        name = (s == 0) ? "" : section_name[s]
        if (count[name] == 0) continue

        if (name != "") {
            icon = ""
            if (name ~ /Docker/)                 icon = "\360\237\220\263 "
            else if (name ~ /Swarm|Container/)    icon = "\360\237\232\200 "
            else if (name ~ /Test/)               icon = "\360\237\247\252 "
            else if (name ~ /Lint/)               icon = "\360\237\224\216 "
            else if (name ~ /Clean/)              icon = "\360\237\247\271 "
            else if (name ~ /Environment|Install/) icon = "\360\237\223\246 "
            else if (name ~ /i18n/)               icon = "\360\237\214\220 "
            else if (name ~ /Version|Release/)    icon = "\360\237\224\226 "
            else if (name ~ /Info|Misc/)          icon = "\342\204\271\357\270\217 "
            print "\033[1m" icon name "\033[0m"
        }

        m = count[name]
        for (i = 1; i <= m; i++) sorted[i] = target[name SUBSEP i]
        asort(sorted)
        for (i = 1; i <= m; i++) {
            printf "  \033[36m%-20s\033[0m %s\n", sorted[i], desc[sorted[i] SUBSEP name]
        }
        print ""
        delete sorted
    }
}
