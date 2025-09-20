import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { trigger, state, style, transition, animate } from '@angular/animations';
import {
  IonContent,
  IonHeader,
  IonTitle,
  IonToolbar,
  IonCard,
  IonCardHeader,
  IonCardTitle,
  IonCardSubtitle,
  IonCardContent,
  IonItem,
  IonInput,
  IonTextarea,
  IonSelect,
  IonSelectOption,
  IonCheckbox,
  IonLabel,
  IonButton,
  IonIcon,
  IonButtons,
  IonBackButton,
  ToastController
} from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import {
  checkmarkOutline,
  closeOutline,
  addOutline,
  trashOutline
} from 'ionicons/icons';
import { ApiService } from '../api.service';

interface Rule {
  name: string;
  description: string;
}

interface ScoringCategory {
  name: string;
  description: string;
  points: number;
}

interface Participant {
  id?: string;
  competition_id?: string;
  name: string;
  description: string;
  picture_location: string;
}

interface PointAccumulation {
  win: number;
  lose: number;
  draw: number;
}

interface Competition {
  id?: string;
  name: string;
  author: string;
  date_created?: string;
  logo_location: string;
  is_private: boolean;
  type: string;
  rules: Rule[];
  scoring_categories: ScoringCategory[];
  point_accumulation: PointAccumulation;
  participants: Participant[];
  fixtures: any[];
  league_table: any[];
  posts: any[];
  photos: any[];
  videos: any[];
}

@Component({
  selector: 'app-create-competition',
  templateUrl: './create-competition.page.html',
  styleUrls: ['./create-competition.page.scss'],
  standalone: true,
  animations: [
    trigger('slideInOut', [
      state('in', style({ height: '*', opacity: 1 })),
      state('out', style({ height: '0px', opacity: 0 })),
      transition('in <=> out', animate('300ms ease-in-out'))
    ]),
    trigger('fadeInUp', [
      transition(':enter', [
        style({ opacity: 0, transform: 'translateY(20px)' }),
        animate('300ms ease-out', style({ opacity: 1, transform: 'translateY(0)' }))
      ])
    ])
  ],
  imports: [
    CommonModule,
    FormsModule,
    IonContent,
    IonHeader,
    IonTitle,
    IonToolbar,
    IonCard,
    IonCardHeader,
    IonCardTitle,
    IonCardSubtitle,
    IonCardContent,
    IonItem,
    IonInput,
    IonTextarea,
    IonSelect,
    IonSelectOption,
    IonCheckbox,
    IonLabel,
    IonButton,
    IonIcon,
    IonButtons,
    IonBackButton
  ]
})
export class CreateCompetitionPage implements OnInit {
  activeSection: string = 'basic';
  competition: Competition = {
    name: '',
    author: '',
    logo_location: '',
    is_private: false,
    type: '',
    rules: [],
    scoring_categories: [],
    point_accumulation: {
      win: 3,
      lose: 0,
      draw: 1
    },
    participants: [],
    fixtures: [],
    league_table: [],
    posts: [],
    photos: [],
    videos: []
  };

  isSubmitting = false;

  constructor(
    private apiService: ApiService,
    private router: Router,
    private toastController: ToastController
  ) {
    addIcons({
      checkmarkOutline,
      closeOutline,
      addOutline,
      trashOutline
    });
  }

  ngOnInit() {
    // Initialize with default rule and scoring category
    this.addRule();
    this.addScoringCategory();
    this.addParticipant();
  }

  setActiveSection(section: string) {
    this.activeSection = this.activeSection === section ? '' : section;
  }
  addRule() {
    this.competition.rules.push({
      name: '',
      description: ''
    });
  }

  removeRule(index: number) {
    this.competition.rules.splice(index, 1);
  }

  addScoringCategory() {
    this.competition.scoring_categories.push({
      name: '',
      description: '',
      points: 0
    });
  }

  removeScoringCategory(index: number) {
    this.competition.scoring_categories.splice(index, 1);
  }

  addParticipant() {
    this.competition.participants.push({
      name: '',
      description: '',
      picture_location: ''
    });
  }

  removeParticipant(index: number) {
    this.competition.participants.splice(index, 1);
  }

  async onSubmit() {
    if (this.isSubmitting) return;

    this.isSubmitting = true;

    try {
      // Set the creation date
      this.competition.date_created = new Date().toISOString();

      // Filter out empty rules and scoring categories
      this.competition.rules = this.competition.rules.filter(
        rule => rule.name.trim() !== '' || rule.description.trim() !== ''
      );
      
      this.competition.scoring_categories = this.competition.scoring_categories.filter(
        category => category.name.trim() !== ''
      );

      // Filter out empty participants
      this.competition.participants = this.competition.participants.filter(
        participant => participant.name.trim() !== ''
      );

      // Create the competition
      const response = await this.apiService.createCompetition(this.competition).toPromise();
      
      // Show success message
      const toast = await this.toastController.create({
        message: 'Competition created successfully!',
        duration: 3000,
        color: 'success',
        position: 'top'
      });
      await toast.present();

      // Navigate back to the main page
      this.router.navigate(['/tabs/tab1']);
      
    } catch (error) {
      console.error('Error creating competition:', error);
      
      // Show error message
      const toast = await this.toastController.create({
        message: 'Failed to create competition. Please try again.',
        duration: 3000,
        color: 'danger',
        position: 'top'
      });
      await toast.present();
    } finally {
      this.isSubmitting = false;
    }
  }
}