import type { FC } from 'react';
import { Navigate, Outlet } from 'react-router-dom';

import { Spin } from 'antd';

import { useStaffMe } from '@shared/api/generated';

import { STAFF_LOGIN_PATH } from '../constants';
import type { RequireStaffProps } from './types';

/**
 * Пускает в зону staff только по серверной сессии (/staff/auth/me); роль берётся из ответа сервера.
 * Это удобство интерфейса, а не контроль доступа: все проверки повторяются на сервере (SR-xx).
 */
export const RequireStaff: FC<RequireStaffProps> = ({ roles }) => {
  const { data, error, isPending } = useStaffMe();

  if (isPending) {
    return <Spin fullscreen />;
  }

  if (error || !data || (roles && !roles.includes(data.role))) {
    return <Navigate to={STAFF_LOGIN_PATH} replace />;
  }

  return <Outlet />;
};
