import { Component, Input, NgZone, OnInit, OnChanges, SimpleChanges } from '@angular/core';
import { FormGroup } from '@angular/forms';
import { ActivatedRoute, Params } from '@angular/router';

import { Account } from './account';
import { TransactionService } from './transaction.service';

@Component({
  selector: 'account-detail',
  templateUrl: 'app/account-detail.component.html',
})
export class AccountDetailComponent implements OnInit, OnChanges {
    @Input()
    account: Account;

    private zone: NgZone;
    private basicOptions: Object;
    private progress: number = 0;
    private response: any = {};
    
    ngOnInit() {
        this.zone = new NgZone({ enableLongStackTrace: false });
        
    }

    ngOnChanges(changes: SimpleChanges) {
      if (this.account !== undefined){
          this.basicOptions = {
              url: "http://localhost:8000/api/accounts/" +
                  this.account.id + "/load/",
              customHeaders: {
                'Authorization': 'Basic ' + btoa("dkent:thisisapassword")
              },
              fieldName: "data_file"
          };
      }
    }

    constructor(
        private transactionService: TransactionService,
        private route: ActivatedRoute){

    }

    handleUpload(data: any): void {
        this.zone.run(() => {
            this.response = data;
            this.progress = data.progress.percent / 100;
        });
    }
}
