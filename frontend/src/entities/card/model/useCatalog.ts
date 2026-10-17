import { useGetCatalogCard, useListCatalogCards } from '@shared/api/generated';
import type { ListCatalogCardsParams } from '@shared/api/generated/model';

/**
 * Страница каталога: серверные данные живут только в кэше TanStack Query.
 * @param params фильтры и пагинация
 */
export const useCatalogPage = (params: ListCatalogCardsParams) => useListCatalogCards(params);

/**
 * Одна опубликованная карточка; для черновика, архива и несуществующей сервер отвечает одинаковым 404.
 * @param cardId идентификатор карточки из URL
 */
export const useTeaserCard = (cardId: string) => useGetCatalogCard(cardId);
