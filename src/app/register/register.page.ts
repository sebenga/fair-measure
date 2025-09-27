
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IonContent, IonButton, IonIcon } from "@ionic/angular/standalone";
import { ApiService } from '../api.service';

@Component({
	selector: 'app-register',
	standalone: true,
	imports: [IonIcon, IonContent, CommonModule, FormsModule],
	templateUrl: './register.page.html',
	styleUrls: ['./auth.shared.scss']
})
export class RegisterPage {
	name = '';
	email = '';
	password = '';
	loading = false;
	error = '';

	constructor(private api: ApiService) {}

	onSubmit() {
		this.loading = true;
		this.error = '';
		this.api.register({ name: this.name, email: this.email, password: this.password }).subscribe({
			next: (res) => {
				// Handle successful registration (e.g., show message, redirect)
				this.loading = false;
				// TODO: Implement navigation or success message
			},
			error: (err) => {
				this.loading = false;
				this.error = 'Registration failed. Please try again.';
			}
		});
	}
}
