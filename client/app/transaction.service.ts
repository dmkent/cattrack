import { Injectable } from '@angular/core';
import { Headers, Http, Response, URLSearchParams } from '@angular/http';

import 'rxjs/add/operator/toPromise';

import { Transaction, TransactionPage } from './transaction';
import { Category, CategorySummary } from './category';
import { Account } from './account';
import { Period } from './period';


function tpFromResponse(response: Response): TransactionPage{
    let decoded = response.json();
    let tp = new TransactionPage()
    tp.count = decoded.count;
    tp.transactions = decoded.results as Transaction[];
    return tp;
}


@Injectable()
export class TransactionService {
    private transUrl = 'http://localhost:8000/api/transactions';
    private catUrl = 'http://localhost:8000/api/categories';
    private accountUrl = 'http://localhost:8000/api/accounts';
    private periodUrl = 'http://localhost:8000/api/periods/';
    private authHeader = 'Basic ' + btoa("dkent:thisisapassword");
    private headers = new Headers({
        'Content-Type': 'application/json',
        'Authorization': this.authHeader,
    });

    constructor(private http: Http) { }

    getTransactions(page: number, page_size: number = 10, 
                    category: Category = null, 
                    account: Account = null,
                    from_date: Date = null, 
                    to_date: Date = null): Promise<TransactionPage> {
        let args = new URLSearchParams();
        args.set('page', "" + page);
        args.set('page_size', "" + page_size);
        args.set('format', "json");

        if (category !== null){
            args.set('category', "" + category.id);
        }
        if (account !== null){
            args.set('account', "" + account.id);
        }
        if (from_date !== null){
            args.set('from_date', from_date.toString());
        }
        if (to_date !== null){
            args.set('to_date', to_date.toString());
        }
        return this.http.get(this.transUrl + '/', {search: args})
                   .toPromise()
                   .then(tpFromResponse)
                   .catch(this.handleError);
    }

    getTransactionsSummary(category: Category = null, 
                           account: Account = null,
                           from_date: Date = null, 
                           to_date: Date = null): Promise<CategorySummary[]> {
        let args = new URLSearchParams();
        args.set('format', "json");

        if (category !== null){
            args.set('category', "" + category.id);
        }
        if (account !== null){
            args.set('account', "" + account.id);
        }
        if (from_date !== null){
            args.set('from_date', from_date.toString());
        }
        if (to_date !== null){
            args.set('to_date', to_date.toString());
        }
        return this.http.get(this.transUrl + '/summary/', {search: args})
                   .toPromise()
                   .then(res => res.json() as CategorySummary[])
                   .catch(this.handleError);
    }


    getTransaction(id: number): Promise<Transaction> {
        return this.http.get(this.transUrl + '/' + id)
                   .toPromise()
                   .then(response => response.json())
                   .catch(this.handleError);
    }

    updateTransaction(transaction: Transaction, splits: any = null): Promise<Transaction> {
        const url = `${this.transUrl}/${transaction.id}/`;
        const splitsUrl = url + "split/"

        if (splits !== null && splits.length == 1){
            let new_category = splits[0].category;
            transaction.category = new_category;
        }
        let first_request = (transaction) => {
            return this.http
                .put(url, JSON.stringify(transaction), {headers: this.headers})
                .toPromise()
                .then(() => transaction)
                .catch(this.handleError);
        };
        let second_request = (transaction) => {
            return transaction;
        };
        if (splits !== null && splits.length > 1) {
            second_request = (transaction) => {
                return this.http
                .post(splitsUrl, JSON.stringify(splits), {headers: this.headers})
                .toPromise()
                .then(() => transaction)
                .catch(this.handleError);
            };
        }

        return first_request(transaction)
               .then(() => second_request(transaction));
    }

    categorySuggestions(transaction: Transaction): Promise<Category[]> {
        const url = `${this.transUrl}/${transaction.id}/suggest`
        return this.http.get(url).toPromise()
               .then(res => res.json() as Category[])
               .catch(this.handleError);
    }

    create(descr: string): Promise<Transaction> {
        return this.http
            .post(this.transUrl, JSON.stringify({
                description: descr,
                amount: 43,
                when: "2014-03-02T00:00",
                account: 1,
            }), {headers: this.headers})
            .toPromise()
            .then(res => res.json())
            .catch(this.handleError);
    }

    delete(id: number): Promise<void> {
        let url = `${this.transUrl}/${id}/`;
        return this.http.delete(url, {headers: this.headers})
            .toPromise()
            .then(() => null)
            .catch(this.handleError);
    }

    getCategories(): Promise<Category[]> {
        let args = new URLSearchParams();
        args.set('format', 'json');
        return this.http.get(this.catUrl, {search: args})
                   .toPromise()
                   .then(res => res.json())
                   .catch(this.handleError);
    }

    getAccounts(): Promise<Account[]> {
        let args = new URLSearchParams();
        args.set('format', 'json');
        return this.http.get(this.accountUrl, {search: args})
                   .toPromise()
                   .then(res => res.json())
                   .catch(this.handleError);
    }

    getPeriods(): Promise<Period[]> {
        let args = new URLSearchParams();
        args.set('format', 'json');
        return this.http.get(this.periodUrl, {search: args})
                   .toPromise()
                   .then(res => res.json() as Period[])
                   .catch(this.handleError);
    }

    getUploadOptions(account: Account): Object {
        return {
            url: this.accountUrl + "/" +
                 account.id + "/load/",
            customHeaders: {
                'Authorization': this.authHeader,
            },
            fieldName: "data_file",
            filterExtensions: true,
            allowedExtensions: ['ofx'],
            autoUpload: false,
        };
    }

    private handleError(error: any): Promise<any> {
        console.error('An error occured', error);
        return Promise.reject(error.message || error);
    }
}
