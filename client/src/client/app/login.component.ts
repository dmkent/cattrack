import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';

import { TransactionService } from './transaction.service';

class LoginDetails {
    username: string;
    password: string;
}

@Component({
  moduleId: module.id,
  selector: 'login-component',
  templateUrl: 'login.component.html'
})
export class LoginComponent implements OnInit {
    details: LoginDetails;

    constructor(
        private transactionService: TransactionService,
        private router: Router) {}

    ngOnInit(): void {
        this.transactionService.logout();
        this.details = new LoginDetails();
    }

    submit() {
        this.transactionService.login(this.details)
            .then(res => this.router.navigate(['']));
    }
}
