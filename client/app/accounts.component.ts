import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';

import { Account } from './account';
import { TransactionService } from './transaction.service';

@Component({
  selector: 'account-list',
  templateUrl: 'app/accounts.component.html',
})
export class AccountComponent implements OnInit {
    accounts: Account[] = [];
    selectedAccount: Account;

    constructor(
        private transactionService: TransactionService,
        private router: Router){}

    ngOnInit(): void {
        this.transactionService.getAccounts()
            .then(accounts => this.accounts = accounts);
    }

    selectAccount(account: Account): void {
        this.selectedAccount = account;
    }
}
