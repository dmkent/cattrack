import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { HttpModule } from '@angular/http';
import { async } from '@angular/core/testing';
import { Route } from '@angular/router';
import { RouterTestingModule } from '@angular/router/testing';

import { NgFileSelectDirective } from 'ng2-uploader';

import { TransactionService } from './transaction.service';
import { AccountComponent } from './accounts.component';
import { AccountDetailComponent } from './account-detail.component';
import { MockTransactionService } from './transaction-service.mock';

export function main() {
  describe('Account component', () => {
    // setting module for testing
    // Disable old forms
    beforeEach(() => {
      let config: Route[] = [
        { path: 'accounts', component: AccountComponent }
      ];
      this.service = new MockTransactionService();

      TestBed.configureTestingModule({
        imports: [FormsModule, RouterModule, HttpModule,
                  RouterTestingModule.withRoutes(config)],
        declarations: [TestComponent, AccountComponent, AccountDetailComponent,
                       NgFileSelectDirective],
        providers: [
          {provide: TransactionService, useValue: this.service}
        ]
      });
    });

    it('should work',
      async(() => {
        TestBed
          .compileComponents()
          .then(() => {
            let fixture = TestBed.createComponent(TestComponent);
            fixture.detectChanges();

            let accountsInstance = fixture.debugElement.children[0].componentInstance;
            let accountsDOMEl = fixture.debugElement.children[0].nativeElement;

            let acct = this.service.ACCOUNTS[0];
            expect(accountsInstance.selectedAccount).toEqual(null);
            accountsInstance.selectAccount(acct);
            expect(accountsInstance.selectedAccount).toEqual(acct);
            accountsInstance.clearAccount();
            expect(accountsInstance.selectedAccount).toEqual(null);

            expect(accountsInstance.transactionService).toEqual(jasmine.any(MockTransactionService));
            expect(accountsDOMEl.querySelectorAll('ul li').length).toEqual(this.service.ACCOUNTS.length);

          });

      }));
  });
}

@Component({
  selector: 'test-cmp',
  template: '<account-list></account-list>'
})
class TestComponent { }
