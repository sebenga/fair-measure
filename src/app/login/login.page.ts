import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IonContent, IonButton, IonItem, IonLabel, IonIcon } from '@ionic/angular/standalone';
import { Router } from '@angular/router';
import { NavController } from '@ionic/angular';
import { AuthService } from '../services/auth.service';

@Component({
	selector: 'app-login',
	standalone: true,
	imports: [IonIcon, IonLabel, IonItem, IonContent, CommonModule, FormsModule, IonButton],
	templateUrl: './login.page.html',
	styleUrls: ['./auth.shared.scss'],
})
export class LoginPage {
	email = '';
	password = '';
	loading = false;
	error = '';

	private readonly homeRoute = '/home';

	constructor(
		private auth: AuthService,
		private router: Router,
		private navCtrl: NavController
	) {}

	onSubmit() {
		this.loading = true;
		this.error = '';
		this.auth.login({ email: this.email, password: this.password }).subscribe({
			next: async () => {
				this.loading = false;
				if (!this.auth.isLoggedIn()) {
					this.error = 'Login succeeded but the session could not be saved.';
					return;
				}
				const ok = await this.router.navigateByUrl(this.homeRoute, { replaceUrl: true });
				if (!ok) {
					await this.navCtrl.navigateRoot(this.homeRoute, { animated: false });
				}
			},
			error: (err) => {
				this.loading = false;
				this.error = err?.message || 'Login failed. Please check your credentials.';
			},
		});
	}
}
