import { Component, ViewContainerRef } from '@angular/core';
@Component({
  selector: 'my-app',
  template: `
    <nav class="navbar navbar-default">
    <div class="container-fluid">
    <div class="navbar-header">
      <a class="navbar-brand" href="#/">CatTrack</a>
    </div>
    <ul class="nav nav-tabs">
        <li><a routerLink="/dashboard" routerLinkActive="active">Dashboard</a></li>
        <li><a routerLink="/accounts" routerLinkActive="active">Accounts</a></li>
        <li><a routerLink="/transactions" routerLinkActive="active">Transactions</a></li>
    </ul>
    </div>
    </nav>
    <div class="container">
    <h1>{{title}}</h1>
    <router-outlet></router-outlet>
    </div>
  `,
  //styleUrls: ['app/app.component.css']
})
export class AppComponent {
  title = 'CatTrack';

  private viewContainerRef: ViewContainerRef;

  public constructor(viewContainerRef:ViewContainerRef) {
    // You need this small hack in order to catch application root view container ref
    this.viewContainerRef = viewContainerRef;
  }
}
