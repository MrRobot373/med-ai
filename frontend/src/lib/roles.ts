import type { Role } from "@/api/types";

/** Writes to the clinical record: notes, prescriptions, orders, problems. */
export const canChart = (role?: Role) => role === "admin" || role === "clinician";
/** Reads clinical content and AI output — everyone except the front desk. */
export const canSeeClinical = (role?: Role) => !!role && role !== "front_desk";
/** Registration, report uploads and the day list. */
export const isStaff = (role?: Role) => role === "admin" || role === "clinician" || role === "front_desk";
export const isFrontDesk = (role?: Role) => role === "front_desk";
