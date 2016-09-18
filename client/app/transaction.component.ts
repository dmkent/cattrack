import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';

import { Transaction } from './transaction';
import { TransactionService } from './transaction.service';

@Component({
  selector: 'my-transactions',
  templateUrl: 'app/transaction.component.html',
    //styleUrls: ['app/transaction.component.css']
})
export class TransactionComponent implements OnInit {
    title = "CatTrack";
    subtitle = "Track spending by category.";
    transactions: Transaction[];
    selectedTransaction: Transaction;

    constructor(
      private transactionService: TransactionService,
      private router: Router){ }

    ngOnInit(): void {
        this.getTransactions();
    }

    onSelect(transaction: Transaction): void {
        this.selectedTransaction = transaction;
    }

    getTransactions(): void {
        this.transactionService.getTransactions().then(transactions => this.transactions = transactions);
    }

    gotoDetail(): void {
      this.router.navigate(['/detail', this.selectedTransaction.id]);
    }

    add(description: string): void {
      description = description.trim();
      if (!description) { return; }
      this.transactionService.create(description)
        .then(trans => {
          this.transactions.push(trans);
          this.selectedTransaction = null;
        });
    }

    delete(transaction: Transaction): void {
      this.transactionService
           .delete(transaction.id)
           .then(() => {
             this.transactions = this.transactions.filter(t => t !== transaction);
        if (this.selectedTransaction === transaction) { this.selectedTransaction = null; }
      });
}

 }