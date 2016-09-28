import { ModuleWithProviders }  from '@angular/core';
import { Routes, RouterModule } from '@angular/router';

import { LoginComponent } from './login.component';
import { LoggedInGuard } from './logged-in.guard';
import { TransactionComponent } from './transaction.component';
import { TransactionDetailComponent } from './transaction-detail.component';
import { DashboardComponent } from './dashboard.component';
import { AccountComponent } from './accounts.component';

const appRoutes: Routes = [
    {
        path: 'transactions',
        component: TransactionComponent,
        canActivate: [LoggedInGuard]
    },
    {
        path: 'dashboard',
        component: DashboardComponent,
        canActivate: [LoggedInGuard]
    },
    {
        path: 'accounts',
        component: AccountComponent,
        canActivate: [LoggedInGuard]
    },
    {
        path: 'login',
        component: LoginComponent
    },
    {
        path: '',
        redirectTo: '/dashboard',
        pathMatch: 'full'
    },
    {
        path: 'detail/:id',
        component: TransactionDetailComponent
    },


];

export const routing: ModuleWithProviders = RouterModule.forRoot(appRoutes);
