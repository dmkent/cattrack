import { Component, Input } from '@angular/core';
import { ActivatedRoute, Params } from '@angular/router';

import { Account } from './account';
import { TransactionService } from './transaction.service';

@Component({
  selector: 'account-detail',
  templateUrl: 'app/account-detail.component.html',
})
export class AccountDetailComponent {
    @Input()
    account: Account;

    constructor(
      private transactionService: TransactionService,
      private route: ActivatedRoute){

    }

    save(): void {
      //this.transactionService.update(this.account)
          //.then(this.goBack);
    }
}
