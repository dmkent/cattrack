import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';

import { Transaction } from './transaction';
import { Account } from './account';
import { Category } from './category';
import { TransactionService } from './transaction.service';
import { CategoriserComponent } from './categoriser.component';

@Component({
  selector: 'my-transactions',
  templateUrl: 'app/transaction.component.html',
    //styleUrls: ['app/transaction.component.css']
})
export class TransactionComponent implements OnInit {
    title = "CatTrack";
    subtitle = "Track spending by category.";
    transactions: Transaction[];
    categories: Category[];
    accounts: Account[];
    count: number = 1;
    page: number = 1;
    page_size: number = 20;
    selectedTransaction: Transaction;
    filterCategory: Category = null;
    filterFrom: Date = null;
    filterTo: Date = null;
    filterAccount: Account = null;
    loading: boolean = false;

    constructor(
      private transactionService: TransactionService,
      private router: Router){ }

    ngOnInit(): void {
        this.getTransactions(this.page);
        this.getCategories();
        this.getAccounts();
    }

    onSelect(transaction: Transaction): void {
        this.selectedTransaction = transaction;
    }

    setFilterCategory(category: Category): void {
        this.filterCategory = category;
        this.page = 1;
        this.getTransactions(this.page);
    }

    setFilterAccount(account: Account): void {
        this.filterAccount = account;
        this.page = 1;
        this.getTransactions(this.page);
    }

    updateFilters(): void {
        this.page = 1;
        this.getTransactions(this.page);
    }

    getTransactions(page?: number): void {
        if (page === undefined){
            page = this.page;
        }
        this.loading = true;
        this.transactionService.getTransactions(page, this.page_size, 
                                                this.filterCategory,
                                                this.filterAccount,
                                                this.filterFrom, this.filterTo).then(res => {
          this.transactions = res.transactions;
          this.count = res.count;
          this.page = page;
          this.loading = false;
        });
    }

    getCategories(): void {
        this.transactionService.getCategories().then(res => this.categories = res);
    }

    getAccounts(): void {
        this.transactionService.getAccounts().then(res => this.accounts = res);
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