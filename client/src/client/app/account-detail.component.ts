import { Component, Input, Output, NgZone, OnInit, SimpleChanges, EventEmitter, ViewChild } from '@angular/core';
import { FormGroup, NgForm, FormControlDirective } from '@angular/forms';
import { ActivatedRoute, Params } from '@angular/router';

import { Account } from './account';
import { TransactionService } from './transaction.service';

@Component({
  moduleId: module.id,
  selector: 'account-detail',
  templateUrl: 'account-detail.component.html',
})
export class AccountDetailComponent implements OnInit {
    @Input()
    account: Account;

    @Output() 
    onReset: EventEmitter<any> = new EventEmitter();

    private zone: NgZone;
    private uploadEvents: EventEmitter<any> = new EventEmitter();
    private progress: number = 0;
    private result: any = {};
    private loading: boolean = false;
    
    ngOnInit() {
        this.zone = new NgZone({ enableLongStackTrace: false });
    }

    constructor(
        private transactionService: TransactionService,
        private route: ActivatedRoute){

    }

    startUpload() {
        this.loading = true;
        this.uploadEvents.emit('startUpload');
    }

    handleUpload(data: any): void {
        this.zone.run(() => {
            this.progress = data.progress.percent;
            if (data.error || data.abort || (data.done && data.status != 200)){
                this.result = {
                    error: true,
                    success: false,
                    message: 'Failed to upload data: ' + data.response
                };
                this.loading = false;
                this.reset();
            }
            else if ( data.done ){
                this.result = {
                    error: false,
                    success: true,
                    message: 'Successfully loaded data.'
                };
                this.loading = false;
                this.reset();
            }
            else {
                this.result = null
            }
        });
    }

    reset() {
        this.account = null;
        this.onReset.emit();
    }
}
