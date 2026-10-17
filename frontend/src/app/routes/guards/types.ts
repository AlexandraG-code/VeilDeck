/** Параметры guard зоны staff: допустимые роли (если не заданы, достаточно любой сессии сотрудника). */
export interface RequireStaffProps {
  roles?: string[];
}
