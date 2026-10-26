# Presentation regression checks using an in-memory modified real bundle.
# This is not a newly rendered report or a change to saved scientific results.
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args) == 1L)
bundle_path <- normalizePath(args[1], mustWork=TRUE)
setwd("scripts/health_pipeline/templates")
source("report_helpers.R")
b <- read_bundle(bundle_path)

stopifnot(identical(format_pct(NA_real_), "Not available"))
stopifnot(identical(format_pct(0, 1), "+0.0%"))
stopifnot(identical(format_pct(-100, 1), "-100.0%"))

topic <- group_topics(b)[1]
stopifnot(length(topic) == 1L, !is.na(topic))
baseline <- b$series$topic == topic &
            b$series$year == b$cfg$reference_year
metric <- b$metrics$metric_id == paste0(topic, ":reference_change")
stopifnot(sum(baseline) == 1L, sum(metric) == 1L)

b$series$value[baseline] <- 0
b$metrics$value[metric] <- NA_real_
disease <- unname(label_topic(b, topic))
table <- monitoring_table(b)
row <- table[table$Disease == disease, , drop=FALSE]
stopifnot(nrow(row) == 1L)
stopifnot(identical(row$Change, "Not available"))
stopifnot(identical(row$Note, "Small numbers: interpret with caution"))

cat("PASS: unavailable percentages remain distinct from zero and -100%.\n")
cat("PASS: institution table labels a zero-reference percentage as Not available.\n")
