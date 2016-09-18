import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';

import { Transaction } from './transaction';
import { TransactionService } from './transaction.service';

@Component({
  selector: 'my-dashboard',
  templateUrl: 'app/dashboard.component.html',
  //styleUrls: ['app/dashboard.component.css']
})
export class DashboardComponent implements OnInit { 
    transactions: Transaction[] = [];

    constructor(
        private transactionService: TransactionService,
        private router: Router){}

    ngOnInit(): void {
        this.transactionService.getTransactions(1)
            .then(transactions => this.transactions = transactions.transactions.slice(1, 5));
    }

    gotoDetail(transaction: Transaction): void {
        let link = ['/detail', transaction.id];
        this.router.navigate(link)
    }
}
