# Notes

Decision composition with deny-wins strategy: when any input decision has allow=false,
the composed result MUST be allow=false. The reasons from all denying decisions are
collected and included in the output. Reasons from allowing decisions are discarded.
Final allow=false, reasons=[R_ACL_DENY_ROLE].
