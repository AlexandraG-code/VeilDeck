import type { EnumGroup } from '../model/types';

/**
 * Ключ i18n подписи значения enum карточки (пространство catalog).
 * @param group группа значений
 * @param value значение из контракта API
 */
export const enumLabelKey = (group: EnumGroup, value: string): string => `enums.${group}.${value}`;
