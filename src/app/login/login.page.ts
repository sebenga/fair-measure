
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IonContent, IonButton } from "@ionic/angular/standalone";
import { ApiService } from '../api.service';

@Component({
	selector: 'app-login',
	standalone: true,
	imports: [IonContent, CommonModule, FormsModule],
	templateUrl: './login.page.html',
	styleUrls: ['./auth.shared.scss']
})
export class LoginPage {
	email = '';
	password = '';
	loading = false;
	error = '';

	constructor(private api: ApiService) {}

	onSubmit() {
		this.loading = true;
		this.error = '';
		this.api.login({ email: this.email, password: this.password }).subscribe({
			next: (res) => {
				// Handle successful login (e.g., store token, redirect)
				this.loading = false;
				// TODO: Implement navigation or token storage
			},
			error: (err) => {
				this.loading = false;
				this.error = 'Login failed. Please check your credentials.';
			}
		});
	}
}
