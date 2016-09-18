import { Injectable } from '@angular/core';
import { Headers, Http, Response } from '@angular/http';

import 'rxjs/add/operator/toPromise';

import { Transaction } from './transaction';
import { TRANSACTIONS } from './mock-transactions'

export class TransactionPage{
    count: number;
    transactions: Transaction[];
}
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
    private headers = new Headers({
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + btoa("dkent:thisisapassword")
    });

    constructor(private http: Http) { }
    
    getTransactions(page: number, page_size: number = 10): Promise<TransactionPage> {
        return this.http.get(this.transUrl + '/?page=' + page + '&page_size=' + page_size)
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

    private handleError(error: any): Promise<any> {
        console.error('An error occured', error);
        return Promise.reject(error.message || error);
    }
}