import type { TeaserCard } from '@shared/api/generated/model';

/** Параметры карточки в списке или на странице; без onOpen карточка не кликабельна (страница деталей). */
export interface CardTeaserProps {
  card: TeaserCard;
  onOpen?: (cardId: string) => void;
}
