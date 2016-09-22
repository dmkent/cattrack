import { ModuleWithProviders }  from '@angular/core';
import { Routes, RouterModule } from '@angular/router';

import { TransactionComponent } from './transaction.component';
import { TransactionDetailComponent } from './transaction-detail.component';
import { DashboardComponent } from './dashboard.component';
import { AccountComponent } from './accounts.component';

const appRoutes: Routes = [
    {
        path: 'transactions',
        component: TransactionComponent
    },
    {
        path: 'dashboard',
        component: DashboardComponent
    },
    {
        path: 'accounts',
        component: AccountComponent
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
