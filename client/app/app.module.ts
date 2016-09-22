import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { HttpModule } from '@angular/http';
import { Ng2BootstrapModule } from 'ng2-bootstrap/ng2-bootstrap';
import { Ng2PaginationModule } from 'ng2-pagination';
import 'jquery';
import { ModalModule } from 'ng2-bootstrap/ng2-bootstrap';

import { routing } from './app.routing';
import { AppComponent } from './app.component';
import { TransactionDetailComponent } from './transaction-detail.component';
import { TransactionComponent } from './transaction.component';
import { TransactionService } from './transaction.service';
import { DashboardComponent } from './dashboard.component';
import { CategoriserComponent } from './categoriser.component';

@NgModule({
  imports:      [ 
    BrowserModule,
    FormsModule,
    ReactiveFormsModule,
    HttpModule,
    routing,
    Ng2BootstrapModule,
    Ng2PaginationModule,
    ModalModule
  ],
  declarations: [ 
    AppComponent,
    TransactionDetailComponent,
    TransactionComponent,
    DashboardComponent,
    CategoriserComponent
  ],
  providers: [
    TransactionService
  ],
  bootstrap:    [ AppComponent ]
})
export class AppModule { }
