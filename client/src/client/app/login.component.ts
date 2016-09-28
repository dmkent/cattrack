import { Component, OnInit } from '@angular/core';

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
        private transactionService: TransactionService) {}

    ngOnInit(): void {
        this.details = new LoginDetails();
    }

    submit() {
        this.transactionService.login(this.details);
    }
}
