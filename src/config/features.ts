const parseTenantList = (value?: string) =>
  value
    ?.split(",")
    .map((tenant) => tenant.trim())
    .filter(Boolean) ?? [];

const isGlobalRollout = (value?: string) => value === "enabled";

export const features = {
  contactsOptIn: {
    enabled: isGlobalRollout(import.meta.env.VITE_CONTACTS_OPT_IN_ROLLOUT),
    pilotTenants: parseTenantList(import.meta.env.VITE_CONTACTS_OPT_IN_TENANTS),
    fallback: "legacy-consent-flow",
  },
};

export const isContactsOptInEnabled = (tenantId?: string) => {
  const { enabled, pilotTenants } = features.contactsOptIn;

  if (!enabled) {
    return false;
  }

  if (!tenantId) {
    return pilotTenants.length === 0;
  }

  return pilotTenants.length === 0 || pilotTenants.includes(tenantId);
};
