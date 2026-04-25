/** Deep links into Yandex Direct DNA (ulogin + entity ids). */

export function dnaAccountHref(ulogin: string): string {
  return `https://direct.yandex.ru/dna/grid/campaigns?ulogin=${encodeURIComponent(ulogin)}`;
}

export function dnaCampaignHref(ulogin: string, campaignId: string): string {
  return `https://direct.yandex.ru/dna/campaigns-edit?ulogin=${encodeURIComponent(
    ulogin,
  )}&campaigns-ids=${encodeURIComponent(campaignId)}`;
}

export function dnaGroupHref(ulogin: string, campaignId: string, groupId: string): string {
  return `https://direct.yandex.ru/dna/groups-edit?ulogin=${encodeURIComponent(ulogin)}&campaigns-ids=${encodeURIComponent(
    campaignId,
  )}&groups-ids=${encodeURIComponent(groupId)}`;
}

export function dnaBannerHref(ulogin: string, campaignId: string, groupId: string, bannerId: string): string {
  return `https://direct.yandex.ru/dna/banners-edit?ulogin=${encodeURIComponent(
    ulogin,
  )}&campaigns-ids=${encodeURIComponent(campaignId)}&groups-ids=${encodeURIComponent(
    groupId,
  )}&banners-ids=${encodeURIComponent(bannerId)}`;
}
