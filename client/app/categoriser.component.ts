import { Component, Input, OnInit, ViewChild } from '@angular/core';
import { Validators, FormGroup, FormArray, FormBuilder, Validator } from '@angular/forms';
import { ModalDirective } from 'ng2-bootstrap/ng2-bootstrap';

import { Transaction } from './transaction';
import { Category } from './category';
import { TransactionService } from './transaction.service';


let totalAmountValidator = (expected: number) => {
    return (g: FormGroup) => {
        let total: number = +0;
        for (let split of g.controls['splits'].value){
            total += +split.amount;
        }
        if (total != expected){
            return {'amountTotalIncorrect': true};
        }
        return null;
    }
};

@Component({
  selector: 'categoriser-component',
  templateUrl: 'app/categoriser.component.html',
})
export class CategoriserComponent implements OnInit {
    @Input()
    transaction: Transaction = null;
    categories: Category[];

    public catForm: FormGroup;

    @ViewChild('catmodal') public childModal:ModalDirective;

    constructor(private transactionService: TransactionService,
                private formBuilder: FormBuilder){}

    ngOnInit(): void {
        this.catForm = this.formBuilder.group({
            splits: this.formBuilder.array([
                this.initSplitCats(true),
            ])
        });
        this.transactionService.getCategories()
              .then(cats => this.categories = cats);
    }

    initSplitCats(isFirst: boolean = false) {
        let init_amount = '';
        let init_cat = null;
        if (isFirst && this.transaction !== undefined) {
            init_amount = "" + this.transaction.amount;
            init_cat = "" + this.transaction.category;
        }
        return this.formBuilder.group({
            category: [init_cat, Validators.required],
            amount: [init_amount, Validators.required]
        });
    }

    addSplitCat() {
        const control = <FormArray>this.catForm.controls['splits']
        control.push(this.initSplitCats());
    }

    removeSplitCat(i: number) {
        const control = <FormArray>this.catForm.controls['splits']
        control.removeAt(i);
    }

    resetSplitCat() {
        this.catForm.controls['splits'] = this.formBuilder.array([
            this.initSplitCats(true),
        ]);
    }

    show(transaction: Transaction){
        this.transaction = transaction;
        this.catForm.setValidators(totalAmountValidator(this.transaction.amount));
        this.resetSplitCat();
        this.childModal.show();
    }

    save(): void {
      let model = this.catForm;
      this.transactionService.updateTransaction(this.transaction,
                                                this.catForm.value)
                             .then(this.hide);
    }

    hide(): void {
      this.childModal.hide();
    }
}