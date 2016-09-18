import { NgModule }      from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms';
import { HttpModule }    from '@angular/http';
import { Ng2BootstrapModule } from 'ng2-bootstrap/ng2-bootstrap';
import {Ng2PaginationModule} from 'ng2-pagination';

import { routing } from './app.routing';
import { AppComponent }   from './app.component';
import { TransactionDetailComponent } from './transaction-detail.component';
import { TransactionComponent } from './transaction.component';
import { TransactionService } from './transaction.service';
import { DashboardComponent }      from './dashboard.component';

@NgModule({
  imports:      [ 
    BrowserModule,
    FormsModule,
    HttpModule,
    routing,
    Ng2BootstrapModule,
    Ng2PaginationModule
  ],
  declarations: [ 
    AppComponent,
    TransactionDetailComponent,
    TransactionComponent,
    DashboardComponent
  ],
  providers: [
    TransactionService
  ],
  bootstrap:    [ AppComponent ]
})
export class AppModule { }
