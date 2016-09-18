import { Component, Input, OnInit } from '@angular/core';
import { ActivatedRoute, Params } from '@angular/router';

import { Transaction } from './transaction';
import { TransactionService } from './transaction.service';

@Component({
  selector: 'my-transaction-detail',
  templateUrl: 'app/transaction-detail.component.html',
  //styleUrls: ['app/transaction-detail.component.css']
})
export class TransactionDetailComponent implements OnInit {
    @Input()
    transaction: Transaction;

    constructor(
      private transactionService: TransactionService,
      private route: ActivatedRoute){

    }

    ngOnInit(): void {
      this.route.params.forEach((params: Params) => {
        let id = + params['id'];
        this.transactionService.getTransaction(id)
            .then(trans => this.transaction = trans);
      });
    }

    save(): void {
      this.transactionService.update(this.transaction)
          .then(this.goBack);
    }

    goBack(): void {
      window.history.back();
    }
}
