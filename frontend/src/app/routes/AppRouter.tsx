import type { FC } from 'react';
import { RouterProvider, createBrowserRouter } from 'react-router-dom';

import { HomePage } from '@pages/home';

const router = createBrowserRouter([{ path: '/', element: <HomePage /> }]);

/** Маршрутизация приложения; зоны viewer/staff и guards добавляются вместе с их страницами. */
export const AppRouter: FC = () => <RouterProvider router={router} />;
