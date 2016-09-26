import { Component } from '@angular/core';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { TestBed } from '@angular/core/testing';
import { APP_BASE_HREF } from '@angular/common';

import {
  async
} from '@angular/core/testing';
import {
  Route
} from '@angular/router';
import {
  RouterTestingModule
} from '@angular/router/testing';

import { Ng2PaginationModule } from 'ng2-pagination';
import { Ng2BootstrapModule } from 'ng2-bootstrap/ng2-bootstrap';
import { ModalModule } from 'ng2-bootstrap/ng2-bootstrap';
import { NgFileSelectDirective } from 'ng2-uploader';

import { AppComponent } from './app.component';
import { DashboardComponent } from './dashboard.component';
import { TransactionComponent } from './transaction.component';
import { AccountDetailComponent } from './account-detail.component';
import { CategoriserComponent } from './categoriser.component';

export function main() {

  describe('App component', () => {

    let config: Route[] = [
      { path: '', component: DashboardComponent },
      { path: 'transactions', component: TransactionComponent }
    ];
    beforeEach(() => {
      TestBed.configureTestingModule({
        imports: [FormsModule, RouterTestingModule.withRoutes(config),
                  Ng2PaginationModule, Ng2BootstrapModule,
                  ModalModule, ReactiveFormsModule],
        declarations: [TestComponent, DashboardComponent,
          TransactionComponent, AppComponent,
          AccountDetailComponent, CategoriserComponent,
          NgFileSelectDirective],
        providers: [
          { provide: APP_BASE_HREF, useValue: '/' }
        ]
      });
    });

    it('should build without a problem',
      async(() => {
        TestBed
          .compileComponents()
          .then(() => {
            let fixture = TestBed.createComponent(TestComponent);
            let compiled = fixture.nativeElement;

            expect(compiled).toBeTruthy();
          });
      }));
  });
}

@Component({
  selector: 'test-cmp',
  template: '<sd-app></sd-app>'
})

class TestComponent {
}



