import { Account } from './account';
import { Transaction } from './transaction';

export class MockTransactionService {
  ACCOUNTS: Account[] = [
    {
      'id': 2,
      'name': 'an account'
    }, {
      'id': 233,
      'name': 'another account'
    }
  ];
  error: any = null;

  getAccounts() {
    return this;
  }

  then(callback: any) {
    if (!this.error) {
      callback(this.ACCOUNTS);
    }
    return this;
  }

  catch(callback: any) {
    if (this.error) {
        callback(this.error);
    }
  }

  setError(error: any) {
    this.error = error;
  }
}
