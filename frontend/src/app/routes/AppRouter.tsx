import type { FC } from 'react';
import { RouterProvider, createBrowserRouter } from 'react-router-dom';

import { AccessPage } from '@pages/access';
import { HomePage } from '@pages/home';
import { StaffHomePage } from '@pages/staff-home';
import { StaffLoginPage } from '@pages/staff-login';
import { ViewerPage } from '@pages/viewer';

import { ACCESS_PATH, HOME_PATH, STAFF_HOME_PATH, STAFF_LOGIN_PATH, VIEWER_PATH } from './constants';
import { RequireStaff } from './guards';

/** Зоны: публичная, viewer (одноразовая ссылка) и staff (вход + guard по серверной сессии). */
export const routes = [
  { path: HOME_PATH, element: <HomePage /> },
  { path: ACCESS_PATH, element: <AccessPage /> },
  { path: VIEWER_PATH, element: <ViewerPage /> },
  { path: STAFF_LOGIN_PATH, element: <StaffLoginPage /> },
  { element: <RequireStaff />, children: [{ path: STAFF_HOME_PATH, element: <StaffHomePage /> }] },
];

const router = createBrowserRouter(routes);

/** Маршрутизация приложения. */
export const AppRouter: FC = () => <RouterProvider router={router} />;
