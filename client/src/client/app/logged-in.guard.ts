import { Injectable } from '@angular/core';
import { Router, CanActivate, ActivatedRouteSnapshot, RouterStateSnapshot } from '@angular/router';

import { TransactionService } from './transaction.service';

@Injectable()
export class LoggedInGuard implements CanActivate {
    constructor(private transactionService: TransactionService,
                private router: Router) {}

    canActivate(route: ActivatedRouteSnapshot, state: RouterStateSnapshot): boolean{
        if (this.transactionService.isLoggedIn()) {
            return true;
        }

        this.router.navigate(['/login']);
        return false;
    }
}
