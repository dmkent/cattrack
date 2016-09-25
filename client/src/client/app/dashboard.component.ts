import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';

import { Transaction } from './transaction';
import { Period } from './period';
import { CategorySummary } from './category';
import { TransactionService } from './transaction.service';

@Component({
  moduleId: module.id,
  selector: 'my-dashboard',
  templateUrl: 'dashboard.component.html'
})
export class DashboardComponent implements OnInit { 
    transactions: Transaction[] = [];
    periods: Period[];
    summaries: CategorySummary[] = null;
    filterFrom: Date = null;
    filterTo: Date = null;

    constructor(
        private transactionService: TransactionService,
        private router: Router){}

    ngOnInit(): void {
        this.transactionService.getTransactions(1)
            .then(transactions => this.transactions = transactions.transactions.slice(1, 5));
        this.transactionService.getPeriods()
            .then(periods => this.periods = periods);
        this.updatePeriod(null, null);
    }

    updatePeriod(from_date: Date, to_date: Date){
        this.filterFrom = from_date;
        this.filterTo = to_date;
        this.transactionService.getTransactionsSummary(null, null, from_date, to_date)
            .then(summaries => this.summaries = summaries);
    }

    gotoDetail(transaction: Transaction): void {
        let link = ['/detail', transaction.id];
        this.router.navigate(link)
    }
}
