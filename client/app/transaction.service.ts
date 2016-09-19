import { Injectable } from '@angular/core';
import { Headers, Http, Response, URLSearchParams } from '@angular/http';

import 'rxjs/add/operator/toPromise';

import { Transaction, TransactionPage } from './transaction';
import { Category } from './category';

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
    private headers = new Headers({
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + btoa("dkent:thisisapassword")
    });

    constructor(private http: Http) { }
    
    getTransactions(page: number, page_size: number = 10, 
                    category: Category = null, from_date: Date = null, 
                    to_date: Date = null): Promise<TransactionPage> {
        let args = new URLSearchParams();
        args.set('page', "" + page);
        args.set('page_size', "" + page_size);

        if (category !== null){
            args.set('category', "" + category.id);
        }
        if (from_date !== null){
            args.set('from_date', from_date.toString();
        }
        if (to_date !== null){
            args.set('to_date', to_date.toString());
        }
        return this.http.get(this.transUrl + '/', {search: args})
                   .toPromise()
                   .then(tpFromResponse)
                   .catch(this.handleError);
    }

    getTransaction(id: number): Promise<Transaction> {
        return this.http.get(this.transUrl + '/' + id)
                   .toPromise()
                   .then(response => response.json())
                   .catch(this.handleError);
    }

    update(transaction: Transaction): Promise<Transaction> {
        const url = `${this.transUrl}/${transaction.id}/`;
        return this.http
            .put(url, JSON.stringify(transaction), {headers: this.headers})
            .toPromise()
            .then(() => transaction)
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
        return this.http.get(this.catUrl)
                   .toPromise()
                   .then(res => res.json())
                   .catch(this.handleError);
    }

    private handleError(error: any): Promise<any> {
        console.error('An error occured', error);
        return Promise.reject(error.message || error);
    }
}