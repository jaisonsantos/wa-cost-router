import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  Contact,
  ContactConsentHistoryResponse,
  ContactListResponse,
  ContactStatus,
  OptInStatus,
} from "@/types/api";

export interface ContactListFilters {
  limit?: number;
  offset?: number;
  status?: ContactStatus;
  channel?: string;
  optInStatus?: OptInStatus[];
  channelAddress?: string;
  segmentIds?: string[];
  segmentSlugs?: string[];
}

const buildContactsParams = (filters: ContactListFilters = {}) => ({
  limit: filters.limit,
  offset: filters.offset,
  status: filters.status,
  channel: filters.channel,
  opt_in_status: filters.optInStatus,
  channel_address: filters.channelAddress,
  segment_id: filters.segmentIds,
  segment_slug: filters.segmentSlugs,
});

export const useContactList = (filters: ContactListFilters = {}) => {
  const params = buildContactsParams(filters);

  return useQuery<ContactListResponse, Error>({
    queryKey: ["contacts", params],
    queryFn: () => api.getContacts(params),
  });
};

export const useContact = (contactId?: string, initialData?: Contact) => {
  return useQuery<Contact, Error>({
    queryKey: ["contact", contactId],
    queryFn: () => api.getContact(contactId as string),
    enabled: Boolean(contactId),
    initialData,
  });
};

export const useContactConsentHistory = (contactId?: string) => {
  return useQuery<ContactConsentHistoryResponse, Error>({
    queryKey: ["contact", contactId, "consent-history"],
    queryFn: () => api.getContactConsentHistory(contactId as string),
    enabled: Boolean(contactId),
  });
};

